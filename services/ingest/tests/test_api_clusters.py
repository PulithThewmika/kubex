"""Tests for cluster management (E22-T1, sub-issues #645-#656)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import NamedTuple
from unittest.mock import AsyncMock, MagicMock

import bcrypt
import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from app.auth import verify_cluster_token
from app.models.cluster import Cluster
from tests.conftest import TEST_ORG_ID, TEST_USER_ID

OTHER_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000099")


def _fake_cluster(
    org_id: uuid.UUID,
    token: str | None = None,
    *,
    cluster_id: uuid.UUID | None = None,
    name: str = "prod-cluster",
    status: str = "pending",
    token_hash_old: str | None = None,
    token_old_expires_at: datetime | None = None,
    last_heartbeat: datetime | None = None,
) -> Cluster:
    return Cluster(
        id=cluster_id or uuid.uuid4(),
        org_id=org_id,
        name=name,
        token_hash=bcrypt.hashpw(token.encode(), bcrypt.gensalt()).decode() if token else "x",
        token_hash_old=token_hash_old,
        token_old_expires_at=token_old_expires_at,
        agent_version=None,
        argocd_version=None,
        argocd_status=None,
        prometheus_status=None,
        last_heartbeat=last_heartbeat,
        status=status,
        created_at=datetime.now(timezone.utc),
    )


# ── S4: create returns the token exactly once ──────────────────────────


class _CreatedRow(NamedTuple):
    id: uuid.UUID
    name: str
    created_at: datetime


@pytest.mark.asyncio
async def test_create_cluster_returns_token_once(client: FastAPI, mock_session: AsyncMock) -> None:
    cluster_id = uuid.uuid4()
    created_at = datetime.now(timezone.utc)
    mock_session.execute = AsyncMock(
        return_value=MagicMock(
            one=MagicMock(return_value=_CreatedRow(id=cluster_id, name="prod-cluster", created_at=created_at))
        )
    )

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.post("/api/clusters", json={"name": "prod-cluster"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(cluster_id)
    assert data["name"] == "prod-cluster"
    assert data["token"].startswith("kbx_")


@pytest.mark.asyncio
async def test_create_cluster_requires_session(client: FastAPI) -> None:
    from app.auth_middleware import get_current_user

    client.dependency_overrides.pop(get_current_user, None)

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.post("/api/clusters", json={"name": "prod-cluster"})
    assert resp.status_code == 401


# ── S5: list scopes to the caller's org, never leaks token/hash ────────


@pytest.mark.asyncio
async def test_list_clusters_never_leaks_token_hash(client: FastAPI, mock_session: AsyncMock) -> None:
    cluster = _fake_cluster(TEST_ORG_ID, "kbx_secret-token-value", status="connected")
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[cluster]))))
    )

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/api/clusters")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "prod-cluster"
    assert data[0]["status"] == "connected"
    body_str = resp.text
    assert "token" not in data[0]
    assert cluster.token_hash not in body_str


@pytest.mark.asyncio
async def test_list_clusters_requires_session(client: FastAPI) -> None:
    from app.auth_middleware import get_current_user

    client.dependency_overrides.pop(get_current_user, None)

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/api/clusters")
    assert resp.status_code == 401


# ── S7: POST /api/clusters/heartbeat ────────────────────────────────────


@pytest.mark.asyncio
async def test_heartbeat_updates_status_and_fields(client: FastAPI, mock_session: AsyncMock) -> None:
    token = "kbx_" + "a" * 40
    cluster = _fake_cluster(TEST_ORG_ID, token, status="pending")
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[cluster]))))
    )

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/clusters/heartbeat",
            headers={"Authorization": f"Bearer {token}"},
            json={"agent_version": "1.2.3", "argocd_status": "healthy", "prometheus_status": "up"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "connected"
    assert data["last_heartbeat"] is not None
    assert cluster.status == "connected"
    assert cluster.agent_version == "1.2.3"
    assert cluster.argocd_status == "healthy"
    assert cluster.prometheus_status == "up"
    assert cluster.last_heartbeat is not None


@pytest.mark.asyncio
async def test_heartbeat_rejects_invalid_token(client: FastAPI, mock_session: AsyncMock) -> None:
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
    )

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.post("/api/clusters/heartbeat", headers={"Authorization": "Bearer kbx_nope"}, json={})

    assert resp.status_code == 401


# ── S6: verify_cluster_token / POST /api/clusters/verify ────────────────


def _session_with_clusters(clusters: list[Cluster]) -> AsyncMock:
    session = AsyncMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=clusters))))
    )
    return session


@pytest.mark.asyncio
async def test_verify_cluster_token_accepts_valid_token() -> None:
    token = "kbx_" + "a" * 40
    cluster = _fake_cluster(TEST_ORG_ID, token)
    session = _session_with_clusters([cluster])

    result = await verify_cluster_token(authorization=f"Bearer {token}", session=session)
    assert result.id == cluster.id


@pytest.mark.asyncio
async def test_verify_cluster_token_rejects_wrong_token() -> None:
    cluster = _fake_cluster(TEST_ORG_ID, "kbx_" + "a" * 40)
    session = _session_with_clusters([cluster])

    with pytest.raises(HTTPException) as exc_info:
        await verify_cluster_token(authorization="Bearer kbx_wrong-token-value", session=session)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_cluster_token_rejects_malformed_header() -> None:
    session = _session_with_clusters([])

    with pytest.raises(HTTPException) as exc_info:
        await verify_cluster_token(authorization="not-a-bearer-header", session=session)
    assert exc_info.value.status_code == 401

    with pytest.raises(HTTPException) as exc_info:
        await verify_cluster_token(authorization=None, session=session)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_cluster_endpoint_returns_config(client: FastAPI, mock_session: AsyncMock) -> None:
    token = "kbx_" + "a" * 40
    cluster = _fake_cluster(TEST_ORG_ID, token, name="prod-cluster")
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[cluster]))))
    )

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.post("/api/clusters/verify", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(cluster.id)
    assert data["name"] == "prod-cluster"
    assert data["org_id"] == str(TEST_ORG_ID)


@pytest.mark.asyncio
async def test_verify_cluster_endpoint_rejects_invalid_token(client: FastAPI, mock_session: AsyncMock) -> None:
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
    )

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.post("/api/clusters/verify", headers={"Authorization": "Bearer kbx_nope"})

    assert resp.status_code == 401
