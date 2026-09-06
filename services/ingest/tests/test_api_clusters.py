"""Tests for cluster management (E22-T1, sub-issues #645-#656)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import NamedTuple
from unittest.mock import AsyncMock, MagicMock

import bcrypt
import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from app.auth import verify_cluster_token
from app.models.cluster import Cluster
from app.models.cluster_query import ClusterQuery
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


def _integrity_error(sqlstate: str | None) -> "IntegrityError":
    from sqlalchemy.exc import IntegrityError

    orig = Exception("db error")
    orig.sqlstate = sqlstate
    return IntegrityError("stmt", {}, orig)


@pytest.mark.asyncio
async def test_create_cluster_rejects_duplicate_name_with_409(client: FastAPI, mock_session: AsyncMock) -> None:
    mock_session.execute = AsyncMock(side_effect=_integrity_error("23505"))
    mock_session.rollback = AsyncMock()

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.post("/api/clusters", json={"name": "prod-cluster"})

    assert resp.status_code == 409
    mock_session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_cluster_reraises_non_duplicate_integrity_error(client: FastAPI, mock_session: AsyncMock) -> None:
    """Only the (org_id, name) unique violation (sqlstate 23505) should be
    mapped to 409 — anything else (a FK/NOT NULL/check violation) must not
    be mislabeled as a name collision. ASGITransport re-raises unhandled
    app exceptions to the caller by default, so the un-mapped IntegrityError
    surfaces here rather than as a response."""
    from sqlalchemy.exc import IntegrityError

    mock_session.execute = AsyncMock(side_effect=_integrity_error("23503"))  # foreign_key_violation
    mock_session.rollback = AsyncMock()

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        with pytest.raises(IntegrityError):
            await ac.post("/api/clusters", json={"name": "prod-cluster"})

    mock_session.rollback.assert_awaited_once()


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

    stmt = mock_session.execute.await_args.args[0]
    assert stmt.compile().params["org_id_1"] == TEST_ORG_ID


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
    """cluster_heartbeat issues a Core UPDATE (not ORM attribute
    assignment) so the write always lands even if a concurrent sweep
    already committed a different status against this same row — see
    test_cluster_lifecycle_integration.py for the real-Postgres proof.
    A mocked session can't observe a DB write, so assert on the executed
    statement's bound values instead of a mutated Python object."""
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

    update_stmt = mock_session.execute.await_args_list[-1].args[0]
    params = update_stmt.compile().params
    assert params["status"] == "connected"
    assert params["agent_version"] == "1.2.3"
    assert params["argocd_status"] == "healthy"
    assert params["prometheus_status"] == "up"
    assert params["last_heartbeat"] is not None


@pytest.mark.asyncio
async def test_heartbeat_rejects_invalid_token(client: FastAPI, mock_session: AsyncMock) -> None:
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
    )

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.post("/api/clusters/heartbeat", headers={"Authorization": "Bearer kbx_nope"}, json={})

    assert resp.status_code == 401


# ── S8: GET /api/clusters/:id/queries ────────────────────────────────────


def _fake_query(cluster_id: uuid.UUID, promql: str = 'up{service="orders"}', status: str = "pending") -> ClusterQuery:
    return ClusterQuery(
        id=uuid.uuid4(),
        cluster_id=cluster_id,
        promql=promql,
        status=status,
        result=None,
        requested_at=datetime.now(timezone.utc),
        completed_at=None,
    )


@pytest.mark.asyncio
async def test_list_pending_queries_returns_only_pending_for_this_cluster(
    client: FastAPI, mock_session: AsyncMock
) -> None:
    token = "kbx_" + "a" * 40
    cluster = _fake_cluster(TEST_ORG_ID, token)
    query = _fake_query(cluster.id, promql='up{service="orders"}')
    mock_session.execute = AsyncMock(
        side_effect=[
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[cluster])))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[query])))),
        ]
    )

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get(f"/api/clusters/{cluster.id}/queries", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == str(query.id)
    assert data[0]["promql"] == 'up{service="orders"}'


@pytest.mark.asyncio
async def test_list_pending_queries_rejects_token_for_a_different_cluster(
    client: FastAPI, mock_session: AsyncMock
) -> None:
    token = "kbx_" + "a" * 40
    cluster = _fake_cluster(TEST_ORG_ID, token)
    other_cluster_id = uuid.uuid4()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[cluster]))))
    )

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get(f"/api/clusters/{other_cluster_id}/queries", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 403


# ── S9: POST /api/clusters/:id/results ───────────────────────────────────


@pytest.mark.asyncio
async def test_submit_query_result_marks_completed(client: FastAPI, mock_session: AsyncMock) -> None:
    token = "kbx_" + "a" * 40
    cluster = _fake_cluster(TEST_ORG_ID, token)
    query_id = uuid.uuid4()
    mock_session.execute = AsyncMock(
        side_effect=[
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[cluster])))),
            MagicMock(rowcount=1),
        ]
    )

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.post(
            f"/api/clusters/{cluster.id}/results",
            headers={"Authorization": f"Bearer {token}"},
            json={"query_id": str(query_id), "result": {"value": 1}},
        )

    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_submit_query_result_404_for_unknown_query(client: FastAPI, mock_session: AsyncMock) -> None:
    token = "kbx_" + "a" * 40
    cluster = _fake_cluster(TEST_ORG_ID, token)
    mock_session.execute = AsyncMock(
        side_effect=[
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[cluster])))),
            MagicMock(rowcount=0),
        ]
    )

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.post(
            f"/api/clusters/{cluster.id}/results",
            headers={"Authorization": f"Bearer {token}"},
            json={"query_id": str(uuid.uuid4()), "result": {}},
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_submit_query_result_rejects_token_for_a_different_cluster(
    client: FastAPI, mock_session: AsyncMock
) -> None:
    token = "kbx_" + "a" * 40
    cluster = _fake_cluster(TEST_ORG_ID, token)
    other_cluster_id = uuid.uuid4()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[cluster]))))
    )

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.post(
            f"/api/clusters/{other_cluster_id}/results",
            headers={"Authorization": f"Bearer {token}"},
            json={"query_id": str(uuid.uuid4()), "result": {}},
        )

    assert resp.status_code == 403


# ── S10: POST /api/clusters/:id/rotate-token ──────────────────────────────


@pytest.mark.asyncio
async def test_rotate_token_returns_new_token_and_grace_expiry(client: FastAPI, mock_session: AsyncMock) -> None:
    cluster = _fake_cluster(TEST_ORG_ID, "kbx_" + "a" * 40, cluster_id=uuid.uuid4())
    original_hash = cluster.token_hash
    mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=cluster)))

    before = datetime.now(timezone.utc)
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.post(f"/api/clusters/{cluster.id}/rotate-token")
    after = datetime.now(timezone.utc)

    assert resp.status_code == 200
    data = resp.json()
    assert data["token"].startswith("kbx_")
    assert cluster.token_hash != original_hash
    assert cluster.token_hash_old == original_hash
    assert cluster.token_old_expires_at is not None
    expected_min = before + timedelta(minutes=10) - timedelta(seconds=2)
    expected_max = after + timedelta(minutes=10) + timedelta(seconds=2)
    assert expected_min <= cluster.token_old_expires_at <= expected_max


@pytest.mark.asyncio
async def test_rotate_token_requires_session(client: FastAPI) -> None:
    from app.auth_middleware import get_current_user

    client.dependency_overrides.pop(get_current_user, None)

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.post(f"/api/clusters/{uuid.uuid4()}/rotate-token")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_rotate_token_404_for_other_orgs_cluster(client: FastAPI, mock_session: AsyncMock) -> None:
    mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.post(f"/api/clusters/{uuid.uuid4()}/rotate-token")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_old_token_still_verifies_within_grace_period_after_rotation() -> None:
    """End-to-end through both auth paths: rotate, then confirm the OLD
    token still authenticates (grace period) and the NEW token also
    authenticates — both valid at once, exactly what the grace period
    is for."""
    old_token = "kbx_" + "old" * 15
    new_token = "kbx_" + "new" * 15
    cluster = _fake_cluster(TEST_ORG_ID, old_token, cluster_id=uuid.uuid4())

    # Simulate what rotate_cluster_token does to the row.
    cluster.token_hash_old = cluster.token_hash
    cluster.token_old_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    cluster.token_hash = bcrypt.hashpw(new_token.encode(), bcrypt.gensalt()).decode()

    session_for_old = _session_with_clusters([cluster])
    result_old = await verify_cluster_token(authorization=f"Bearer {old_token}", session=session_for_old)
    assert result_old.id == cluster.id

    session_for_new = _session_with_clusters([cluster])
    result_new = await verify_cluster_token(authorization=f"Bearer {new_token}", session=session_for_new)
    assert result_new.id == cluster.id


@pytest.mark.asyncio
async def test_old_token_rejected_once_grace_period_expires() -> None:
    old_token = "kbx_" + "old" * 15
    new_token = "kbx_" + "new" * 15
    cluster = _fake_cluster(TEST_ORG_ID, old_token, cluster_id=uuid.uuid4())

    cluster.token_hash_old = cluster.token_hash
    cluster.token_old_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)  # already expired
    cluster.token_hash = bcrypt.hashpw(new_token.encode(), bcrypt.gensalt()).decode()

    session = _session_with_clusters([cluster])
    with pytest.raises(HTTPException) as exc_info:
        await verify_cluster_token(authorization=f"Bearer {old_token}", session=session)
    assert exc_info.value.status_code == 401


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
