"""Tests for GET /api/settings/installations (E21-T4-S2)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.models.installation import Installation
from tests.conftest import TEST_ORG_ID


def _fake_installation(status: str = "active") -> Installation:
    return Installation(
        id=uuid.uuid4(),
        org_id=TEST_ORG_ID,
        github_installation_id=12345,
        account_login="acme-corp",
        repos=["acme-corp/kubex", "acme-corp/sample-app"],
        status=status,
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_list_installations_returns_org_installations(client: FastAPI, mock_session: AsyncMock) -> None:
    installation = _fake_installation()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[installation]))))
    )

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/api/settings/installations")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["account_login"] == "acme-corp"
    assert data[0]["github_installation_id"] == 12345
    assert data[0]["repos"] == ["acme-corp/kubex", "acme-corp/sample-app"]
    assert data[0]["status"] == "active"


@pytest.mark.asyncio
async def test_list_installations_empty(client: FastAPI, mock_session: AsyncMock) -> None:
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
    )

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/api/settings/installations")

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_installations_requires_session(client: FastAPI) -> None:
    from app.auth_middleware import get_current_user

    client.dependency_overrides.pop(get_current_user, None)

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/api/settings/installations")

    assert resp.status_code == 401
