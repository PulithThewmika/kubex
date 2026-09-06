"""Tests for the GitHub App webhook handler."""

import json
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.dialects import postgresql

from tests.conftest import TEST_ORG_ID


def _table_of(stmt):
    table = getattr(stmt, "table", None)
    if table is not None:
        return table.name
    descriptions = getattr(stmt, "column_descriptions", None)
    if descriptions:
        return descriptions[0]["entity"].__tablename__
    return None


def _installation_created_payload(installation_id=42, account_login="acme", account_id=999):
    return {
        "action": "created",
        "installation": {"id": installation_id, "account": {"id": account_id, "login": account_login}},
        "repositories": [{"full_name": "acme/orders"}],
    }


def _workflow_run_app_payload(installation_id=42, action="requested", head_sha="abc1234567890", run_id=555):
    return {
        "action": action,
        "installation": {"id": installation_id},
        "repository": {"full_name": "acme/orders"},
        "workflow_run": {
            "id": run_id,
            "head_sha": head_sha,
            "head_branch": "main",
            "actor": {"login": "octocat"},
            "head_commit": {"timestamp": "2026-08-01T10:00:00Z"},
            "run_started_at": "2026-08-01T10:00:00Z",
            "updated_at": "2026-08-01T10:05:00Z",
        },
    }


async def _post_app_event(app, payload_dict, event_type, sign_fn):
    payload = json.dumps(payload_dict).encode()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        return await ac.post(
            "/webhooks/github/app",
            content=payload,
            headers={
                "X-Hub-Signature-256": sign_fn(payload),
                "X-GitHub-Event": event_type,
                "Content-Type": "application/json",
            },
        )


@pytest.mark.asyncio
async def test_installation_created_stores_row_linked_to_org(client, mock_session, sign_github_app_payload):
    """installation.created must resolve the org via account.id ->
    organizations.github_org_id and upsert the installations row under
    that org (E21-T2-S3/S10)."""
    executed_statements = []
    original_execute = mock_session.execute

    async def capture_execute(stmt):
        executed_statements.append(stmt)
        return await original_execute(stmt)

    mock_session.execute = capture_execute

    resp = await _post_app_event(
        client, _installation_created_payload(), "installation", sign_github_app_payload,
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "installation": "created"}

    installation_stmts = [s for s in executed_statements if _table_of(s) == "installations"]
    assert len(installation_stmts) == 1
    compiled = installation_stmts[0].compile(dialect=postgresql.dialect())
    params = compiled.params
    assert params["github_installation_id"] == 42
    assert params["account_login"] == "acme"
    assert params["org_id"] == TEST_ORG_ID


@pytest.mark.asyncio
async def test_workflow_run_creates_deployment_under_resolved_org(client, mock_session, sign_github_app_payload):
    """workflow_run delivered via the GitHub App must resolve org_id from
    installations (not the classic repo-based lookup) and still create a
    deployment through the shared correlation logic (E21-T2-S8/S11)."""

    async def mock_execute(stmt):
        table = _table_of(stmt)
        result = MagicMock()
        if table == "installations":
            result.scalar_one_or_none.return_value = TEST_ORG_ID
        elif table == "services":
            result.scalars.return_value.all.return_value = []
        elif table == "deployments":
            result.scalar_one.return_value = 7
        return result

    mock_session.execute = mock_execute

    resp = await _post_app_event(
        client, _workflow_run_app_payload(action="requested"), "workflow_run", sign_github_app_payload,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["deployment_status"] == "building"


@pytest.mark.asyncio
async def test_workflow_run_unknown_installation_ignored(client, mock_session, sign_github_app_payload):
    async def mock_execute(stmt):
        result = MagicMock()
        if _table_of(stmt) == "installations":
            result.scalar_one_or_none.return_value = None
        return result

    mock_session.execute = mock_execute

    resp = await _post_app_event(
        client, _workflow_run_app_payload(), "workflow_run", sign_github_app_payload,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"
