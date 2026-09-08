"""Tests for webhook authentication — HMAC (GitHub) and bearer token (ArgoCD)."""

import json
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import bcrypt
import pytest
from httpx import ASGITransport, AsyncClient

from app.auth import validate_auth_tokens, verify_argocd_token
from app.models.cluster import Cluster


@pytest.mark.asyncio
async def test_github_valid_signature(client, sign_github_payload):
    payload = json.dumps({
        "action": "requested",
        "workflow_run": {"id": 1, "head_sha": "abc1234", "head_branch": "main", "actor": {"login": "user"}},
        "repository": {"full_name": "org/repo"},
    }).encode()

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.post(
            "/webhooks/github",
            content=payload,
            headers={
                "X-Hub-Signature-256": sign_github_payload(payload),
                "X-GitHub-Event": "workflow_run",
                "Content-Type": "application/json",
            },
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_github_missing_signature(client):
    payload = json.dumps({"action": "requested"}).encode()

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.post(
            "/webhooks/github",
            content=payload,
            headers={"X-GitHub-Event": "workflow_run", "Content-Type": "application/json"},
        )
    assert resp.status_code == 401
    assert "Missing" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_github_bad_signature(client):
    payload = json.dumps({"action": "requested"}).encode()

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.post(
            "/webhooks/github",
            content=payload,
            headers={
                "X-Hub-Signature-256": "sha256=badbadbadbad",
                "X-GitHub-Event": "workflow_run",
                "Content-Type": "application/json",
            },
        )
    assert resp.status_code == 401
    assert "Invalid" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_argocd_valid_token(client, argocd_token):
    payload = json.dumps({
        "type": "on-sync-succeeded",
        "app": {"metadata": {"name": "sample-app"}, "status": {"sync": {"revision": "abc1234"}, "operationState": {}}},
    })

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.post(
            "/webhooks/argocd",
            content=payload,
            headers={
                "Authorization": f"Bearer {argocd_token}",
                "Content-Type": "application/json",
            },
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Bug #115: requires fix/115-argocd-auth-401 to be merged", strict=False)
async def test_argocd_missing_auth_returns_401(client):
    """Regression test for bug #115 — was returning 422."""
    payload = json.dumps({"type": "on-sync-succeeded", "app": {"metadata": {"name": "test"}}})

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.post(
            "/webhooks/argocd",
            content=payload,
            headers={"Content-Type": "application/json"},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_argocd_bad_token_returns_401(client):
    payload = json.dumps({"type": "on-sync-succeeded", "app": {"metadata": {"name": "test"}}})

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.post(
            "/webhooks/argocd",
            content=payload,
            headers={
                "Authorization": "Bearer wrong-token",
                "Content-Type": "application/json",
            },
        )
    assert resp.status_code == 401


# ── per-cluster ArgoCD tokens (#found 2026-09-08) ────────────────────
# The legacy path above resolves org_id by matching an existing services
# row's argocd_app name, which misattributes a newly-connected cluster's
# deployments to whichever org first registered that app name. A
# per-cluster token instead identifies the exact org via the clusters
# table, closing that cross-tenant gap.

def _make_cluster(raw_token: str, org_id: uuid.UUID | None = None) -> Cluster:
    cluster = Cluster(
        id=uuid.uuid4(),
        org_id=org_id or uuid.uuid4(),
        name="test-cluster",
        token_hash=bcrypt.hashpw(raw_token.encode(), bcrypt.gensalt()).decode(),
        status="connected",
    )
    return cluster


@pytest.mark.asyncio
async def test_verify_argocd_token_accepts_global_secret_returns_none(argocd_token):
    session = AsyncMock()
    result = await verify_argocd_token(authorization=f"Bearer {argocd_token}", session=session)
    assert result is None
    session.execute.assert_not_called()  # global match is a fast path — no cluster DB walk


@pytest.mark.asyncio
async def test_verify_argocd_token_accepts_per_cluster_token():
    raw_token = "kbx_test_cluster_token"
    org_id = uuid.uuid4()
    cluster = _make_cluster(raw_token, org_id=org_id)

    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [cluster]
    session.execute = AsyncMock(return_value=result_mock)

    result = await verify_argocd_token(authorization=f"Bearer {raw_token}", session=session)
    assert result is cluster
    assert result.org_id == org_id


@pytest.mark.asyncio
async def test_verify_argocd_token_rejects_unknown_token():
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []  # no clusters registered
    session.execute = AsyncMock(return_value=result_mock)

    with pytest.raises(Exception) as exc_info:
        await verify_argocd_token(authorization="Bearer totally-unknown", session=session)
    assert "401" in str(exc_info.value) or getattr(exc_info.value, "status_code", None) == 401


@pytest.mark.asyncio
async def test_argocd_webhook_per_cluster_token_uses_cluster_org(client, mock_session):
    """End-to-end: a per-cluster-authenticated event resolves its service
    within that cluster's own org, not the argocd_app-name-matched default
    org the legacy path would fall back to."""
    raw_token = "kbx_test_cluster_token_e2e"
    cluster_org_id = uuid.uuid4()
    cluster = _make_cluster(raw_token, org_id=cluster_org_id)

    def execute_side_effect(stmt, params=None):
        if "token_hash" in str(stmt):
            result = MagicMock()
            result.scalars.return_value.all.return_value = [cluster]
            return result
        return MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    mock_session.execute = AsyncMock(side_effect=execute_side_effect)

    payload = json.dumps({
        "type": "on-sync-succeeded",
        "app": {"metadata": {"name": "sample-app"}, "status": {"sync": {"revision": "abc1234"}, "operationState": {}}},
    })

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.post(
            "/webhooks/argocd",
            content=payload,
            headers={"Authorization": f"Bearer {raw_token}", "Content-Type": "application/json"},
        )
    assert resp.status_code == 200

    # The PipelineEvent insert is the first write — confirm it carries the
    # cluster's org_id, not a default/legacy-resolved one. Compile without
    # literal_binds and read .params directly — the payload column is
    # JSONB, which the generic dialect can't literal-render, but bound
    # params are plain Python values regardless of column type.
    pipeline_event_org_ids = []
    for call in mock_session.execute.call_args_list:
        stmt = call.args[0]
        if "pipeline_events" in str(stmt).lower():
            pipeline_event_org_ids.append(stmt.compile().params.get("org_id"))
    assert pipeline_event_org_ids, "expected a pipeline_events insert"
    assert cluster_org_id in pipeline_event_org_ids, (
        f"expected cluster org_id {cluster_org_id} in pipeline_events insert, got {pipeline_event_org_ids}"
    )


def test_validate_auth_tokens_raises_on_empty_github():
    """Startup rejects empty GITHUB_WEBHOOK_SECRET."""
    with patch("app.auth.GITHUB_WEBHOOK_SECRET", ""):
        with pytest.raises(RuntimeError, match="GITHUB_WEBHOOK_SECRET"):
            validate_auth_tokens()


def test_validate_auth_tokens_raises_on_empty_argocd():
    """Startup rejects empty ARGOCD_WEBHOOK_TOKEN."""
    with patch("app.auth.ARGOCD_WEBHOOK_TOKEN", ""):
        with pytest.raises(RuntimeError, match="ARGOCD_WEBHOOK_TOKEN"):
            validate_auth_tokens()


def test_validate_auth_tokens_raises_on_empty_alertmanager():
    """Startup rejects empty ALERTMANAGER_WEBHOOK_TOKEN."""
    with patch("app.auth.ALERTMANAGER_WEBHOOK_TOKEN", ""):
        with pytest.raises(RuntimeError, match="ALERTMANAGER_WEBHOOK_TOKEN"):
            validate_auth_tokens()


def test_validate_auth_tokens_raises_on_empty_mcp_internal_token():
    """Startup rejects empty MCP_INTERNAL_TOKEN (#840 — internal relay auth)."""
    with patch("app.auth.MCP_INTERNAL_TOKEN", ""):
        with pytest.raises(RuntimeError, match="MCP_INTERNAL_TOKEN"):
            validate_auth_tokens()
