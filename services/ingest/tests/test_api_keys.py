"""Tests for API key management (E19-T4, sub-issues #562-#566)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import NamedTuple
from unittest.mock import AsyncMock, MagicMock

import bcrypt
import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.auth import verify_api_key
from app.models.api_key import ApiKey
from tests.conftest import TEST_ORG_ID, TEST_USER_ID

OTHER_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000099")


def _fake_key(org_id: uuid.UUID, token: str, key_id: uuid.UUID | None = None) -> ApiKey:
    key = ApiKey(
        id=key_id or uuid.uuid4(),
        org_id=org_id,
        name="ci",
        token_hash=bcrypt.hashpw(token.encode(), bcrypt.gensalt()).decode(),
        last_used=None,
        created_at=datetime.now(timezone.utc),
    )
    return key


# ── S1: create returns the token exactly once ────────────────────────


class _CreatedRow(NamedTuple):
    id: uuid.UUID
    name: str
    created_at: datetime


@pytest.mark.asyncio
async def test_create_api_key_returns_token_once(client, mock_session):
    key_id = uuid.uuid4()
    created_at = datetime.now(timezone.utc)
    mock_session.execute = AsyncMock(
        return_value=MagicMock(one=MagicMock(return_value=_CreatedRow(id=key_id, name="ci", created_at=created_at)))
    )

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.post("/api/settings/api-keys", json={"name": "ci"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(key_id)
    assert data["name"] == "ci"
    assert data["token"].startswith("dl_")


@pytest.mark.asyncio
async def test_create_api_key_requires_session(client):
    from app.auth_middleware import get_current_user
    client.dependency_overrides.pop(get_current_user, None)

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.post("/api/settings/api-keys", json={"name": "ci"})
    assert resp.status_code == 401


# ── S2: list never leaks token or hash ────────────────────────────────


@pytest.mark.asyncio
async def test_list_api_keys_never_leaks_token_or_hash(client, mock_session):
    key = _fake_key(TEST_ORG_ID, "dl_secret-token-value")
    mock_session.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[key])))))

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/api/settings/api-keys")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "ci"
    assert "token" not in data[0]
    assert "token_hash" not in data[0]
    body_str = resp.text
    assert "dl_secret-token-value" not in body_str
    assert key.token_hash not in body_str


# ── S3: revoke removes access ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_revoke_api_key_deletes_row(client, mock_session):
    mock_session.execute = AsyncMock(return_value=MagicMock(rowcount=1))

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.delete(f"/api/settings/api-keys/{uuid.uuid4()}")

    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_revoke_api_key_not_found_returns_404(client, mock_session):
    mock_session.execute = AsyncMock(return_value=MagicMock(rowcount=0))

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.delete(f"/api/settings/api-keys/{uuid.uuid4()}")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_revoke_api_key_malformed_id_returns_400(client):
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.delete("/api/settings/api-keys/not-a-uuid")

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_crud_routes_require_session_jwt(client):
    from app.auth_middleware import get_current_user
    client.dependency_overrides.pop(get_current_user, None)

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        get_resp = await ac.get("/api/settings/api-keys")
        delete_resp = await ac.delete(f"/api/settings/api-keys/{uuid.uuid4()}")

    assert get_resp.status_code == 401
    assert delete_resp.status_code == 401


# ── S4/S5: verify_api_key ─────────────────────────────────────────────


def _session_with_keys(keys: list[ApiKey]) -> AsyncMock:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=keys)))))
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_verify_api_key_accepts_valid_token_and_returns_org_id():
    token = "dl_" + "a" * 40
    key = _fake_key(TEST_ORG_ID, token)
    session = _session_with_keys([key])

    org_id = await verify_api_key(authorization=f"Bearer {token}", session=session)

    assert org_id == TEST_ORG_ID
    assert key.last_used is not None


@pytest.mark.asyncio
async def test_verify_api_key_rejects_wrong_token():
    key = _fake_key(TEST_ORG_ID, "dl_" + "a" * 40)
    session = _session_with_keys([key])

    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key(authorization="Bearer dl_wrong-token-value", session=session)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_api_key_rejects_revoked_token():
    token = "dl_" + "a" * 40
    session = _session_with_keys([])  # revoked = no longer in the table

    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key(authorization=f"Bearer {token}", session=session)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_api_key_rejects_malformed_header():
    session = _session_with_keys([])

    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key(authorization="not-a-bearer-header", session=session)
    assert exc_info.value.status_code == 401

    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key(authorization=None, session=session)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_api_key_scopes_to_correct_org_not_other_org():
    """A key issued for org A must not authenticate as org B, and must
    not match some other org's key that happens to share nothing but
    the coincidence of being checked in the same pool."""
    token_a = "dl_" + "a" * 40
    token_b = "dl_" + "b" * 40
    key_a = _fake_key(TEST_ORG_ID, token_a)
    key_b = _fake_key(OTHER_ORG_ID, token_b)
    session = _session_with_keys([key_a, key_b])

    org_id = await verify_api_key(authorization=f"Bearer {token_a}", session=session)
    assert org_id == TEST_ORG_ID

    org_id_b = await verify_api_key(authorization=f"Bearer {token_b}", session=session)
    assert org_id_b == OTHER_ORG_ID
