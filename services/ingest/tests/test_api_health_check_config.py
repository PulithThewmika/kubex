"""Tests for PUT /api/services/{name}/health-check (E23-T1-S5)."""

from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient


def _mock_row(name="orders", url="https://orders.example.com/health", interval=30):
    row = MagicMock()
    row.name = name
    row.health_check_url = url
    row.health_check_interval_s = interval
    return row


@pytest.mark.asyncio
async def test_configure_health_check_success(client, mock_session):
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
async def test_configure_health_check_unknown_service_404(client, mock_session):
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
async def test_configure_health_check_rejects_non_http_url(client, mock_session):
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.put(
            "/api/services/orders/health-check",
            json={"health_check_url": "ftp://example.com/health"},
        )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_configure_health_check_defaults_interval(client, mock_session):
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
