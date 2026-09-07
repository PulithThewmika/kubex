"""Tests for PUT /api/services/{name}/health-check (E23-T1-S5)."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

# Matches conftest.py's TEST_ORG_ID — the org the `client` fixture's
# get_current_user override authenticates every request as.
TEST_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


def _mock_row(name: str = "orders", url: str = "https://orders.example.com/health", interval: int = 30) -> MagicMock:
    row = MagicMock()
    row.name = name
    row.health_check_url = url
    row.health_check_interval_s = interval
    return row


@pytest.mark.asyncio
async def test_configure_health_check_success(client: FastAPI, mock_session: AsyncMock) -> None:
    result = MagicMock()
    result.first.return_value = _mock_row()
    mock_session.execute.return_value = result

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.put(
            "/api/services/orders/health-check",
            json={"health_check_url": "https://orders.example.com/health", "health_check_interval_s": 30},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "orders"
    assert data["health_check_url"] == "https://orders.example.com/health"
    assert data["health_check_interval_s"] == 30
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_configure_health_check_unknown_service_404(client: FastAPI, mock_session: AsyncMock) -> None:
    result = MagicMock()
    result.first.return_value = None
    mock_session.execute.return_value = result

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.put(
            "/api/services/nonexistent/health-check",
            json={"health_check_url": "https://example.com/health"},
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_configure_health_check_rejects_non_http_url(client: FastAPI, mock_session: AsyncMock) -> None:
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.put(
            "/api/services/orders/health-check",
            json={"health_check_url": "ftp://example.com/health"},
        )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_configure_health_check_defaults_interval(client: FastAPI, mock_session: AsyncMock) -> None:
    result = MagicMock()
    result.first.return_value = _mock_row(interval=30)
    mock_session.execute.return_value = result

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.put(
            "/api/services/orders/health-check",
            json={"health_check_url": "https://orders.example.com/health"},
        )

    assert resp.status_code == 200
    call_kwargs = mock_session.execute.call_args.args[1]
    assert call_kwargs["interval"] == 30


@pytest.mark.asyncio
async def test_configure_health_check_scopes_update_to_callers_org(client: FastAPI, mock_session: AsyncMock) -> None:
    """The UPDATE's only protection against a cross-org write is its
    `WHERE org_id = :org_id` clause (CLAUDE.md decision 9) — assert the
    query is actually parameterized with the authenticated caller's org,
    not just that the happy path returns 200."""
    result = MagicMock()
    result.first.return_value = _mock_row()
    mock_session.execute.return_value = result

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.put(
            "/api/services/orders/health-check",
            json={"health_check_url": "https://orders.example.com/health"},
        )

    assert resp.status_code == 200
    call_kwargs = mock_session.execute.call_args.args[1]
    assert call_kwargs["org_id"] == TEST_ORG_ID
    assert call_kwargs["name"] == "orders"


@pytest.mark.asyncio
async def test_configure_health_check_rejects_loopback_url(
    client: FastAPI, mock_session: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    # ALLOW_INSECURE_HEALTH_CHECK_URL is read at import time — force it off
    # so this test's 422 assertion holds regardless of the environment
    # it happens to run in.
    monkeypatch.setattr("app.schemas.health_check.ALLOW_INSECURE_HEALTH_CHECK_URL", False)

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.put(
            "/api/services/orders/health-check",
            json={"health_check_url": "http://127.0.0.1:8000/health"},
        )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_configure_health_check_rejects_link_local_metadata_url(
    client: FastAPI, mock_session: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """169.254.169.254 is the cloud metadata endpoint (AWS/GCP) — the
    always-on agent must not be pointable at it (SSRF)."""
    monkeypatch.setattr("app.schemas.health_check.ALLOW_INSECURE_HEALTH_CHECK_URL", False)

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.put(
            "/api/services/orders/health-check",
            json={"health_check_url": "http://169.254.169.254/latest/meta-data/"},
        )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_configure_health_check_rejects_interval_below_agent_tick(client: FastAPI, mock_session: AsyncMock) -> None:
    """The agent only evaluates due-ness once per HEALTH_CHECK_TICK_SECONDS
    (default 15s) — an interval below that would silently not be honored,
    so the API rejects it outright instead of promising a cadence it can't
    deliver."""
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.put(
            "/api/services/orders/health-check",
            json={"health_check_url": "https://orders.example.com/health", "health_check_interval_s": 5},
        )

    assert resp.status_code == 422
