"""Tests for the org-scoped Prometheus relay endpoint (/api/prom, #832)."""

import contextlib
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.routers import prom

_ORG = "11111111-1111-1111-1111-111111111111"
_AUTH = {"Authorization": "Bearer testtok"}


# ── _extract_org unit tests ──────────────────────────────────────────


def test_extract_org_strips_the_matcher():
    org, cluster, cleaned = prom._extract_org(
        f'http_requests_total{{service=~"a|b", org_id="{_ORG}", status=~"5.."}}'
    )
    assert org == _ORG
    assert cluster is None
    assert cleaned == 'http_requests_total{service=~"a|b", status=~"5.."}'


def test_extract_org_trailing_position():
    org, _cluster, cleaned = prom._extract_org(f'up{{service="x",org_id="{_ORG}"}}')
    assert org == _ORG
    assert cleaned == 'up{service="x"}'


def test_extract_org_absent():
    assert prom._extract_org('up{service="x"}') == (None, None, 'up{service="x"}')


def test_extract_org_rejects_ambiguous_multi_org():
    other = "99999999-9999-9999-9999-999999999999"
    assert prom._extract_org(f'a{{org_id="{_ORG}"}} + b{{org_id="{other}"}}') == (None, None, None)


def test_extract_org_strips_every_matcher():
    org, _c, cleaned = prom._extract_org(f'a{{org_id="{_ORG}"}} + b{{x="y",org_id="{_ORG}"}}')
    assert org == _ORG
    assert "org_id" not in cleaned


def test_extract_org_with_cluster_pin():
    cid = "22222222-2222-2222-2222-222222222222"
    org, cluster, cleaned = prom._extract_org(f'up{{org_id="{_ORG}", cluster="{cid}"}}')
    assert (org, cluster) == (_ORG, cid)
    assert "cluster" not in cleaned and "org_id" not in cleaned


# ── relay endpoint tests ─────────────────────────────────────────────


class _FakeSession:
    """Stands in for an AsyncSession from async_session(). scalar() returns
    the next queued value; execute().first() returns the next queued row."""

    def __init__(self, scalars, rows):
        self._scalars = list(scalars)
        self._rows = list(rows)
        self.commit = AsyncMock()

    async def scalar(self, *_a, **_k):
        return self._scalars.pop(0)

    async def execute(self, *_a, **_k):
        result = MagicMock()
        result.first = MagicMock(return_value=self._rows.pop(0) if self._rows else None)
        return result


def _patch_session(scalars=(), rows=()):
    session = _FakeSession(scalars, rows)

    @contextlib.asynccontextmanager
    async def factory():
        yield session

    return patch("app.routers.prom.async_session", factory), session


@pytest.fixture
def _token():
    with patch("app.auth.GRAFANA_DATASOURCE_TOKEN", "testtok"):
        yield


@pytest.fixture(autouse=True)
def _instant_sleep():
    with patch("app.routers.prom._sleep", AsyncMock()):
        yield


async def _get(path, **params):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        return await ac.get(path, params=params, headers=_AUTH)


@pytest.mark.asyncio
async def test_relay_returns_agent_result(_token):
    cluster_id, query_id = uuid.uuid4(), uuid.uuid4()
    completed = MagicMock(status="completed", result={"status": "success", "data": {}})
    ctx, _s = _patch_session(scalars=[cluster_id, query_id], rows=[completed])
    with ctx:
        resp = await _get("/api/prom/api/v1/query", query=f'up{{org_id="{_ORG}"}}')
    assert resp.status_code == 200
    assert resp.json() == {"status": "success", "data": {}}


@pytest.mark.asyncio
async def test_relay_missing_org_matcher_is_bad_data(_token):
    resp = await _get("/api/prom/api/v1/query", query="up")
    assert resp.status_code == 400
    assert resp.json()["errorType"] == "bad_data"


@pytest.mark.asyncio
async def test_relay_multi_org_rejected(_token):
    other = "99999999-9999-9999-9999-999999999999"
    resp = await _get("/api/prom/api/v1/query", query=f'a{{org_id="{_ORG}"}}+b{{org_id="{other}"}}')
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_relay_query_too_long(_token):
    resp = await _get("/api/prom/api/v1/query", query="up" * 3000 + f'{{org_id="{_ORG}"}}')
    assert resp.status_code == 400
    assert "exceeds" in resp.json()["error"]


@pytest.mark.asyncio
async def test_relay_no_connected_cluster(_token):
    ctx, _s = _patch_session(scalars=[None])
    with ctx:
        resp = await _get("/api/prom/api/v1/query", query=f'up{{org_id="{_ORG}"}}')
    assert resp.status_code == 502
    assert resp.json()["errorType"] == "no_metrics_source"


@pytest.mark.asyncio
async def test_relay_timeout_is_distinguishable(_token):
    ctx, session = _patch_session(scalars=[uuid.uuid4(), uuid.uuid4()], rows=[])
    with patch("app.routers.prom.RELAY_TIMEOUT", 0.01), ctx:
        resp = await _get("/api/prom/api/v1/query", query=f'up{{org_id="{_ORG}"}}')
    assert resp.status_code == 504
    assert resp.json()["errorType"] == "timeout"
    # the stale row is cleaned up (DELETE issued + committed)
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_relay_requires_bearer():
    with patch("app.auth.GRAFANA_DATASOURCE_TOKEN", "testtok"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/api/prom/api/v1/query", params={"query": "up"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_relay_unconfigured_token_fails_closed():
    with patch("app.auth.GRAFANA_DATASOURCE_TOKEN", ""):
        resp = await _get("/api/prom/api/v1/query", query="up")
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_range_query_relays_params(_token):
    captured = {}

    async def fake_relay(q, kind, params):
        captured.update(kind=kind, params=params)
        return JSONResponse(content={"ok": True})

    from fastapi.responses import JSONResponse

    with patch("app.routers.prom._relay", fake_relay):
        resp = await _get(
            "/api/prom/api/v1/query_range",
            query=f'up{{org_id="{_ORG}"}}',
            start="1",
            end="2",
            step="15s",
        )
    assert resp.status_code == 200
    assert captured == {"kind": "range", "params": {"start": "1", "end": "2", "step": "15s"}}


@pytest.mark.asyncio
async def test_buildinfo_stub(_token):
    resp = await _get("/api/prom/api/v1/status/buildinfo")
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
