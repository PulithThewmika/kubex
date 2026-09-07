"""Tests for the org members endpoint (E24-T3-S5, Team tab)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import NamedTuple
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from tests.conftest import TEST_ORG_ID


class _MemberRow(NamedTuple):
    id: uuid.UUID
    login: str
    avatar_url: str | None
    role: str
    joined_at: datetime


@pytest.mark.asyncio
async def test_list_members_returns_login_avatar_role(client: FastAPI, mock_session: AsyncMock) -> None:
    rows = [
        _MemberRow(uuid.uuid4(), "alice", "https://avatars/alice", "owner", datetime.now(timezone.utc)),
        _MemberRow(uuid.uuid4(), "bob", None, "member", datetime.now(timezone.utc)),
    ]
    mock_session.execute = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=rows)))

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/api/settings/members")

    assert resp.status_code == 200
    data = resp.json()
    assert [m["login"] for m in data] == ["alice", "bob"]
    assert data[0]["role"] == "owner"
    assert data[1]["avatar_url"] is None


@pytest.mark.asyncio
async def test_list_members_query_filters_on_org(client: FastAPI, mock_session: AsyncMock) -> None:
    mock_session.execute = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[])))

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        await ac.get("/api/settings/members")

    compiled = mock_session.execute.call_args[0][0].compile()
    assert "org_memberships.org_id = " in str(compiled)
    assert TEST_ORG_ID in compiled.params.values()


@pytest.mark.asyncio
async def test_list_members_requires_session(client: FastAPI) -> None:
    from app.auth_middleware import get_current_user

    client.dependency_overrides.pop(get_current_user, None)
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/api/settings/members")
    assert resp.status_code == 401
