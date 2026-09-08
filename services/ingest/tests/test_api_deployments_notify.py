"""Tests for POST /api/deployments/notify (E21-T3-S3/S4/S5/S6)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.dialects import postgresql

from app.auth import verify_api_key
from tests.conftest import TEST_ORG_ID


def _table_of(stmt):
    table = getattr(stmt, "table", None)
    if table is not None:
        return table.name
    descriptions = getattr(stmt, "column_descriptions", None)
    if descriptions:
        return descriptions[0]["entity"].__tablename__
    return None


def _notify_body(**overrides):
    body = {
        "service": "orders",
        "commit_sha": "abc1234567890",
        "status": "success",
        "environment": "production",
        "image_tag": None,
    }
    body.update(overrides)
    return body


@pytest.fixture
def api_key_client(client):
    """Override auth with verify_api_key (org API key), not the session JWT
    get_current_user this endpoint intentionally bypasses."""
    async def override_verify_api_key():
        return TEST_ORG_ID

    client.dependency_overrides[verify_api_key] = override_verify_api_key
    yield client
    client.dependency_overrides.pop(verify_api_key, None)


async def _post_notify(app, body):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        return await ac.post("/api/deployments/notify", json=body)


@pytest.mark.asyncio
async def test_requires_api_key(client):
    resp = await _post_notify(client, _notify_body())
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_creates_orphan_deployment_and_logs_pipeline_event(api_key_client, mock_session):
    existing_service = MagicMock(id=5, org_id=TEST_ORG_ID)
    executed_statements = []

    async def mock_execute(stmt, *args, **kwargs):
        executed_statements.append(stmt)
        table = _table_of(stmt)
        result = MagicMock()
        if table == "services":
            result.scalars.return_value.all.return_value = [existing_service]
        elif table == "deployments":
            result.scalar_one_or_none.return_value = None  # no prior correlating deployment
            result.one.return_value = (100, "deployed")  # RETURNING id, status from the ON CONFLICT insert
        return result

    mock_session.execute = mock_execute

    resp = await _post_notify(api_key_client, _notify_body())
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"status": "ok", "deployment_id": 100, "deployment_status": "deployed", "correlation": "orphan"}

    event_stmts = [s for s in executed_statements if _table_of(s) == "pipeline_events"]
    assert len(event_stmts) == 1
    params = event_stmts[0].compile(dialect=postgresql.dialect()).params
    assert params["source"] == "generic"
    assert params["org_id"] == TEST_ORG_ID

    deployment_inserts = [
        s for s in executed_statements
        if _table_of(s) == "deployments" and getattr(s, "is_insert", False)
    ]
    assert len(deployment_inserts) == 1
    assert deployment_inserts[0]._post_values_clause is not None
    assert deployment_inserts[0].compile(dialect=postgresql.dialect()).params["commit_sha"] == "abc1234567890"

    # The ON CONFLICT arbiter must match V021's actual partial index
    # predicate exactly (commit_sha IS NOT NULL AND workflow_run_id IS
    # NULL) or Postgres won't recognize it as the same index — a rows
    # created by webhooks_github.py's process_workflow_run (which always
    # sets workflow_run_id) must never collide with this index.
    where_sql = str(deployment_inserts[0]._post_values_clause.inferred_target_whereclause)
    assert "commit_sha IS NOT NULL" in where_sql
    assert "workflow_run_id IS NULL" in where_sql


@pytest.mark.asyncio
async def test_duplicate_commit_sha_updates_existing_row_not_a_new_one(api_key_client, mock_session):
    """A second notify for the same commit_sha must correlate to the
    already-created deployment (idempotent via the unique index) rather
    than attempting a second orphan insert."""
    existing_service = MagicMock(id=5, org_id=TEST_ORG_ID)
    existing_deployment = MagicMock(id=100, status="syncing")
    executed_statements = []

    async def mock_execute(stmt, *args, **kwargs):
        executed_statements.append(stmt)
        table = _table_of(stmt)
        result = MagicMock()
        if table == "services":
            result.scalars.return_value.all.return_value = [existing_service]
        elif table == "deployments":
            if getattr(stmt, "is_update", False):
                result.scalar_one_or_none.return_value = "deployed"  # non-terminal -> applied
            else:
                result.scalar_one_or_none.return_value = existing_deployment  # correlation SELECT
        return result

    mock_session.execute = mock_execute

    resp = await _post_notify(api_key_client, _notify_body(status="success"))
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["deployment_id"] == 100
    assert data["deployment_status"] == "deployed"

    # No second Deployment row was inserted — only the correlation SELECT
    # and the guarded UPDATE ran.
    deployment_inserts = [
        s for s in executed_statements
        if _table_of(s) == "deployments" and getattr(s, "is_insert", False)
    ]
    assert deployment_inserts == []


@pytest.mark.asyncio
async def test_terminal_state_not_regressed(api_key_client, mock_session):
    existing_service = MagicMock(id=5, org_id=TEST_ORG_ID)
    existing_deployment = MagicMock(id=100, status="deployed")

    async def mock_execute(stmt, *args, **kwargs):
        table = _table_of(stmt)
        result = MagicMock()
        if table == "services":
            result.scalars.return_value.all.return_value = [existing_service]
        elif table == "deployments":
            if getattr(stmt, "is_update", False):
                result.scalar_one_or_none.return_value = None  # WHERE excluded the already-terminal row
            elif stmt.column_descriptions[0]["name"] == "status":
                result.scalar_one.return_value = existing_deployment.status  # fallback re-query
            else:
                result.scalar_one_or_none.return_value = existing_deployment  # correlation SELECT
        return result

    mock_session.execute = mock_execute

    resp = await _post_notify(api_key_client, _notify_body(status="in_progress"))
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ignored"
    assert data["deployment_status"] == "deployed"


@pytest.mark.asyncio
async def test_rejects_invalid_status_value(api_key_client):
    resp = await _post_notify(api_key_client, {**_notify_body(), "status": "not-a-real-status"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_rejects_empty_service_name(api_key_client):
    """An empty `service` must not silently fall through resolve_service's
    name-derivation default and get merged into a shared 'unknown' service."""
    resp = await _post_notify(api_key_client, {**_notify_body(), "service": ""})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_rejects_empty_commit_sha(api_key_client):
    resp = await _post_notify(api_key_client, {**_notify_body(), "commit_sha": ""})
    assert resp.status_code == 422
