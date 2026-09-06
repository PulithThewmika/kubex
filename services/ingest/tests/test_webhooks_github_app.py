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


def _deployment_status_payload(installation_id=42, state="success", sha="abc1234567890"):
    return {
        "installation": {"id": installation_id},
        "repository": {"full_name": "acme/orders"},
        "deployment": {"sha": sha},
        "deployment_status": {"state": state},
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
async def test_installation_created_conflict_does_not_clobber_repos_or_status(
    client, mock_session, sign_github_app_payload,
):
    """A redelivered installation.created must not reset repos appended by a
    later installation_repositories.added, or reactivate an installation a
    later installation.suspend already turned off — the ON CONFLICT clause
    must only ever refresh account_login."""
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

    installation_stmts = [s for s in executed_statements if _table_of(s) == "installations"]
    on_conflict = installation_stmts[0]._post_values_clause
    updated_columns = {c if isinstance(c, str) else c.name for c, _ in on_conflict.update_values_to_set}
    assert updated_columns == {"account_login"}


@pytest.mark.asyncio
async def test_installation_created_unknown_account_logs_null_org(client, mock_session, sign_github_app_payload):
    """An installation.created for an account with no matching organization
    must still be logged (org_id=NULL — schema allows this since V020) and
    return ignored, not guess an org."""
    executed_statements = []
    original_execute = mock_session.execute

    async def capture_execute(stmt):
        executed_statements.append(stmt)
        return await original_execute(stmt)

    async def mock_execute(stmt):
        executed_statements.append(stmt)
        result = MagicMock()
        if _table_of(stmt) == "organizations":
            result.scalar_one_or_none.return_value = None
        return result

    mock_session.execute = mock_execute

    resp = await _post_app_event(
        client, _installation_created_payload(), "installation", sign_github_app_payload,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"

    event_stmts = [s for s in executed_statements if _table_of(s) == "pipeline_events"]
    assert len(event_stmts) == 1
    assert event_stmts[0].compile(dialect=postgresql.dialect()).params["org_id"] is None


@pytest.mark.asyncio
async def test_deployment_status_does_not_regress_deployed_to_syncing(client, mock_session, sign_github_app_payload):
    existing_service = MagicMock(id=5, org_id=TEST_ORG_ID)
    existing_deployment = MagicMock(id=100, status="deployed")

    async def mock_execute(stmt):
        table = _table_of(stmt)
        result = MagicMock()
        if table == "installations":
            result.scalar_one_or_none.return_value = TEST_ORG_ID
        elif table == "services":
            result.scalars.return_value.all.return_value = [existing_service]
        elif table == "deployments":
            result.scalar_one_or_none.return_value = existing_deployment
        return result

    mock_session.execute = mock_execute

    resp = await _post_app_event(
        client, _deployment_status_payload(state="in_progress"), "deployment_status", sign_github_app_payload,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"
    assert existing_deployment.status == "deployed"


@pytest.mark.asyncio
async def test_deployment_status_does_not_flip_between_terminal_states(client, mock_session, sign_github_app_payload):
    """A stale/reordered 'failure' arriving after 'success' already landed
    must not flip an already-deployed deployment to sync_failed — neither
    deployment_status carries an ordering signal to tell which is newer."""
    existing_service = MagicMock(id=5, org_id=TEST_ORG_ID)
    existing_deployment = MagicMock(id=100, status="deployed")

    async def mock_execute(stmt):
        table = _table_of(stmt)
        result = MagicMock()
        if table == "installations":
            result.scalar_one_or_none.return_value = TEST_ORG_ID
        elif table == "services":
            result.scalars.return_value.all.return_value = [existing_service]
        elif table == "deployments":
            result.scalar_one_or_none.return_value = existing_deployment
        return result

    mock_session.execute = mock_execute

    resp = await _post_app_event(
        client, _deployment_status_payload(state="failure"), "deployment_status", sign_github_app_payload,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"
    assert existing_deployment.status == "deployed"


@pytest.mark.asyncio
async def test_deployment_status_same_state_redelivery_preserves_finished_at(
    client, mock_session, sign_github_app_payload,
):
    """A redelivered 'success' for an already-deployed deployment must not
    bump finished_at to the redelivery time — that would silently change
    the recorded lifecycle duration."""
    existing_service = MagicMock(id=5, org_id=TEST_ORG_ID)
    original_finished_at = "2026-08-01T10:10:00Z"
    existing_deployment = MagicMock(id=100, status="deployed", finished_at=original_finished_at)

    async def mock_execute(stmt):
        table = _table_of(stmt)
        result = MagicMock()
        if table == "installations":
            result.scalar_one_or_none.return_value = TEST_ORG_ID
        elif table == "services":
            result.scalars.return_value.all.return_value = [existing_service]
        elif table == "deployments":
            result.scalar_one_or_none.return_value = existing_deployment
        return result

    mock_session.execute = mock_execute

    resp = await _post_app_event(
        client, _deployment_status_payload(state="success"), "deployment_status", sign_github_app_payload,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"
    assert existing_deployment.finished_at == original_finished_at


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
async def test_deployment_status_orphan_upsert_index_excludes_workflow_run_rows(
    client, mock_session, sign_github_app_payload,
):
    """The ON CONFLICT arbiter on the orphan-creation insert must match
    V021's actual partial index predicate (commit_sha IS NOT NULL AND
    workflow_run_id IS NULL) exactly, so it never collides with rows
    process_workflow_run creates (which always set workflow_run_id) —
    e.g. a manual GitHub Actions re-run of the same commit (/code-review
    high on PR #796)."""
    executed_statements = []

    async def mock_execute(stmt):
        executed_statements.append(stmt)
        table = _table_of(stmt)
        result = MagicMock()
        if table == "installations":
            result.scalar_one_or_none.return_value = TEST_ORG_ID
        elif table == "services":
            result.scalars.return_value.all.return_value = []
        elif table == "deployments":
            result.scalar_one_or_none.return_value = None
        return result

    mock_session.execute = mock_execute

    resp = await _post_app_event(
        client, _deployment_status_payload(state="success"), "deployment_status", sign_github_app_payload,
    )
    assert resp.status_code == 200

    deployment_inserts = [
        s for s in executed_statements
        if _table_of(s) == "deployments" and hasattr(s, "_post_values_clause")
    ]
    assert len(deployment_inserts) == 1
    where_sql = str(deployment_inserts[0]._post_values_clause.inferred_target_whereclause)
    assert "commit_sha IS NOT NULL" in where_sql
    assert "workflow_run_id IS NULL" in where_sql


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
