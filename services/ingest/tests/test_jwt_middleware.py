"""Tests for JWT middleware and protected routes (E19-T3, sub-issues #559/#560)."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("ARGOCD_WEBHOOK_TOKEN", "test-token")
os.environ.setdefault("ALERTMANAGER_WEBHOOK_TOKEN", "test-am-token")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-at-least-32-bytes-long")

from app.main import app  # noqa: E402
from app.db import get_session  # noqa: E402

JWT_SECRET = os.environ["JWT_SECRET"]

USER_ID = str(uuid.uuid4())
ORG_ID = str(uuid.uuid4())


def _make_token(
    user_id: str = USER_ID,
    org_id: str = ORG_ID,
    exp_hours: float = 24,
    secret: str = JWT_SECRET,
) -> str:
    return jwt.encode(
        {
            "user_id": user_id,
            "org_id": org_id,
            "exp": datetime.now(timezone.utc) + timedelta(hours=exp_hours),
        },
        secret,
        algorithm="HS256",
    )


def _expired_token() -> str:
    return jwt.encode(
        {
            "user_id": USER_ID,
            "org_id": ORG_ID,
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        },
        JWT_SECRET,
        algorithm="HS256",
    )


def _tampered_token() -> str:
    return jwt.encode(
        {"user_id": USER_ID, "org_id": ORG_ID, "exp": datetime.now(timezone.utc) + timedelta(hours=24)},
        "wrong-secret-wrong-secret-wrong-secret",
        algorithm="HS256",
    )


@pytest.fixture(autouse=True)
def _no_real_safety_score():
    with patch(
        "app.routers.webhooks_github.compute_safety_score",
        AsyncMock(return_value=(0, {})),
    ):
        yield


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    session.commit = AsyncMock()
    return session


@pytest.fixture
async def client(mock_session):
    async def override_get_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_get_session
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


# ── S9: Unauthenticated → 401, valid JWT → 200 ──────────────────────


@pytest.mark.asyncio
async def test_api_services_no_cookie_returns_401(client):
    resp = await client.get("/api/services")
    assert resp.status_code == 401
    assert "Authentication required" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_api_services_valid_jwt_returns_200(client, mock_session):
    mock_session.execute = AsyncMock(return_value=MagicMock(fetchall=MagicMock(return_value=[])))
    token = _make_token()
    resp = await client.get("/api/services", cookies={"session": token})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_api_deployments_no_cookie_returns_401(client):
    resp = await client.get("/api/deployments")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_api_dora_no_cookie_returns_401(client):
    resp = await client.get("/api/dora")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_api_alerts_no_cookie_returns_401(client):
    resp = await client.get("/api/alerts")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_api_chat_no_cookie_returns_401(client):
    resp = await client.post("/api/chat", json={"messages": [{"role": "user", "content": "hello"}]})
    assert resp.status_code == 401


# ── S10: Expired/tampered JWT → 401 ──────────────────────────────────


@pytest.mark.asyncio
async def test_expired_jwt_returns_401(client):
    resp = await client.get("/api/services", cookies={"session": _expired_token()})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_tampered_jwt_returns_401(client):
    resp = await client.get("/api/services", cookies={"session": _tampered_token()})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_malformed_jwt_returns_401(client):
    resp = await client.get("/api/services", cookies={"session": "not.a.jwt"})
    assert resp.status_code == 401


# ── S8: Webhook routes still work with existing auth (no JWT needed) ─


@pytest.mark.asyncio
async def test_alerts_inbound_uses_bearer_not_jwt(client, mock_session):
    mock_session.execute = AsyncMock(return_value=MagicMock(rowcount=0))
    mock_session.commit = AsyncMock()
    resp = await client.post(
        "/api/alerts/inbound",
        json={"alerts": []},
        headers={"Authorization": f"Bearer {os.environ['ALERTMANAGER_WEBHOOK_TOKEN']}"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_alerts_inbound_without_bearer_returns_401(client):
    resp = await client.post("/api/alerts/inbound", json={"alerts": []})
    assert resp.status_code == 401


# ── Logout (S3) ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_logout_clears_session_cookie(client):
    token = _make_token()
    resp = await client.post("/auth/logout", cookies={"session": token})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    set_cookie = resp.headers.get("set-cookie", "")
    assert "session=" in set_cookie
    assert 'Max-Age=0' in set_cookie or 'expires=' in set_cookie.lower()


# ── Me (S4) ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_me_no_cookie_returns_401(client):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_valid_jwt_returns_profile(client, mock_session):
    user_obj = MagicMock()
    user_obj.login = "testuser"
    user_obj.email = "test@example.com"
    user_obj.avatar_url = "https://avatar.example.com/1"

    org_obj = MagicMock()
    org_obj.name = "TestOrg"
    org_obj.slug = "testorg"

    call_count = 0

    async def _fake_execute(stmt):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            result.scalar_one_or_none = MagicMock(return_value=user_obj)
        else:
            result.scalar_one_or_none = MagicMock(return_value=org_obj)
        return result

    mock_session.execute = _fake_execute

    token = _make_token()
    resp = await client.get("/auth/me", cookies={"session": token})
    assert resp.status_code == 200
    data = resp.json()
    assert data["login"] == "testuser"
    assert data["email"] == "test@example.com"
    assert data["org_name"] == "TestOrg"
    assert data["org_slug"] == "testorg"
    assert data["user_id"] == USER_ID
    assert data["org_id"] == ORG_ID


# ── Switch Org (S5) ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_switch_org_no_cookie_returns_401(client):
    resp = await client.post("/auth/switch-org", json={"org_id": str(uuid.uuid4())})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_switch_org_not_member_returns_403(client, mock_session):
    mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    token = _make_token()
    new_org = str(uuid.uuid4())
    resp = await client.post("/auth/switch-org", json={"org_id": new_org}, cookies={"session": token})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_switch_org_valid_reissues_jwt(client, mock_session):
    membership = MagicMock()
    mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=membership)))
    token = _make_token()
    new_org = str(uuid.uuid4())
    resp = await client.post("/auth/switch-org", json={"org_id": new_org}, cookies={"session": token})
    assert resp.status_code == 200
    assert resp.json()["org_id"] == new_org
    set_cookie = resp.headers.get("set-cookie", "")
    assert "session=" in set_cookie

    cookie_value = None
    for part in set_cookie.split(";"):
        part = part.strip()
        if part.startswith("session="):
            cookie_value = part[len("session="):]
            break
    assert cookie_value
    claims = jwt.decode(cookie_value, JWT_SECRET, algorithms=["HS256"])
    assert claims["org_id"] == new_org
    assert claims["user_id"] == USER_ID


@pytest.mark.asyncio
async def test_switch_org_invalid_org_id_returns_400(client):
    token = _make_token()
    resp = await client.post("/auth/switch-org", json={"org_id": "not-a-uuid"}, cookies={"session": token})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_switch_org_missing_org_id_returns_400(client):
    token = _make_token()
    resp = await client.post("/auth/switch-org", json={}, cookies={"session": token})
    assert resp.status_code == 400
