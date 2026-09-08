"""Tests for the org-scoped Prometheus relay endpoint (/api/prom, #832)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.routers import prom

_ORG = "11111111-1111-1111-1111-111111111111"
_AUTH = {"Authorization": "Bearer testtok"}


def test_extract_org_strips_the_matcher():
    org, cleaned = prom._extract_org(
        f'http_requests_total{{service=~"a|b", org_id="{_ORG}", status=~"5.."}}'
    )
    assert org == _ORG
    assert "org_id" not in cleaned
    assert cleaned == 'http_requests_total{service=~"a|b", status=~"5.."}'


def test_extract_org_trailing_position():
    org, cleaned = prom._extract_org(f'up{{service="x",org_id="{_ORG}"}}')
    assert org == _ORG
    assert cleaned == 'up{service="x"}'


def test_extract_org_absent():
    assert prom._extract_org("up{service=\"x\"}") == (None, 'up{service="x"}')


@pytest.fixture
def _token():
    with patch("app.auth.GRAFANA_DATASOURCE_TOKEN", "testtok"):
        yield


@pytest.fixture
def _instant_sleep():
    with patch("app.routers.prom._sleep", AsyncMock()):
        yield


async def _get(app, path, **params):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        return await ac.get(path, params=params, headers=_AUTH)


@pytest.mark.asyncio
async def test_relay_returns_agent_result(client, mock_session, _token, _instant_sleep):
    mock_session.scalar = AsyncMock(side_effect=[uuid.uuid4(), uuid.uuid4()])
    mock_session.execute.side_effect = None
    mock_session.execute.return_value = MagicMock(
        first=MagicMock(return_value=MagicMock(status="completed", result={"status": "success", "data": {}}))
    )

    resp = await _get(client, "/api/prom/api/v1/query", query=f'up{{org_id="{_ORG}"}}')

    assert resp.status_code == 200
    assert resp.json() == {"status": "success", "data": {}}


@pytest.mark.asyncio
async def test_relay_missing_org_matcher_is_bad_data(client, _token):
    resp = await _get(client, "/api/prom/api/v1/query", query="up")
    assert resp.status_code == 400
    assert resp.json()["errorType"] == "bad_data"


@pytest.mark.asyncio
async def test_relay_no_connected_cluster(client, mock_session, _token):
    mock_session.scalar = AsyncMock(return_value=None)
    resp = await _get(client, "/api/prom/api/v1/query", query=f'up{{org_id="{_ORG}"}}')
    assert resp.status_code == 502
    assert resp.json()["errorType"] == "no_metrics_source"


@pytest.mark.asyncio
async def test_relay_timeout_is_distinguishable(client, mock_session, _token, _instant_sleep):
    mock_session.scalar = AsyncMock(side_effect=[uuid.uuid4(), uuid.uuid4()])
    mock_session.execute.side_effect = None
    mock_session.execute.return_value = MagicMock(
        first=MagicMock(return_value=MagicMock(status="pending", result=None))
    )
    with patch("app.routers.prom.RELAY_TIMEOUT", 0.01):
        resp = await _get(client, "/api/prom/api/v1/query", query=f'up{{org_id="{_ORG}"}}')
    assert resp.status_code == 504
    assert resp.json()["errorType"] == "timeout"


@pytest.mark.asyncio
async def test_relay_requires_bearer(client):
    with patch("app.auth.GRAFANA_DATASOURCE_TOKEN", "testtok"):
        async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
            resp = await ac.get("/api/prom/api/v1/query", params={"query": "up"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_relay_unconfigured_token_fails_closed(client):
    with patch("app.auth.GRAFANA_DATASOURCE_TOKEN", ""):
        resp = await _get(client, "/api/prom/api/v1/query", query="up")
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_range_query_relays_params(client, mock_session, _token, _instant_sleep):
    captured = {}

    async def fake_relay(session, q, kind, params):
        captured["kind"] = kind
        captured["params"] = params
        from fastapi.responses import JSONResponse

        return JSONResponse(content={"ok": True})

    mock_session.scalar = AsyncMock(side_effect=[uuid.uuid4(), uuid.uuid4()])
    with patch("app.routers.prom._relay", fake_relay):
        resp = await _get(
            client,
            "/api/prom/api/v1/query_range",
            query=f'up{{org_id="{_ORG}"}}',
            start="1",
            end="2",
            step="15s",
        )
    assert resp.status_code == 200
    assert captured["kind"] == "range"
    assert captured["params"] == {"start": "1", "end": "2", "step": "15s"}


@pytest.mark.asyncio
async def test_buildinfo_stub(client, _token):
    resp = await _get(client, "/api/prom/api/v1/status/buildinfo")
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
