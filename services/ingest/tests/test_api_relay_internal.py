"""Tests for the internal org-scoped telemetry relay (#840, routers/relay_internal.py)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app import cluster_relay
from tests.conftest import TEST_ORG_ID

AUTH_HEADERS = {"Authorization": "Bearer test-internal-token"}


@pytest.mark.asyncio
async def test_missing_bearer_token_rejected(client: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get(
            "/internal/relay/prometheus/query",
            params={"org_id": str(TEST_ORG_ID), "query": "up"},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_wrong_bearer_token_rejected(client: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get(
            "/internal/relay/prometheus/query",
            params={"org_id": str(TEST_ORG_ID), "query": "up"},
            headers={"Authorization": "Bearer wrong-token"},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_malformed_org_id_returns_bad_data(client: FastAPI, monkeypatch) -> None:
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get(
            "/internal/relay/prometheus/query",
            params={"org_id": "not-a-uuid", "query": "up"},
            headers=AUTH_HEADERS,
        )
    assert resp.status_code == 400
    body = resp.json()
    assert body["status"] == "error"
    assert body["errorType"] == "bad_data"


@pytest.mark.asyncio
async def test_no_connected_cluster_returns_502(client: FastAPI, monkeypatch) -> None:
    async def fake_relay_query(session, org_id, query, kind="instant", params=None, timeout=None):
        raise cluster_relay.NoClusterError(f"org {org_id} has no connected cluster")

    monkeypatch.setattr(cluster_relay, "relay_query", fake_relay_query)

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get(
            "/internal/relay/prometheus/query",
            params={"org_id": str(TEST_ORG_ID), "query": "up"},
            headers=AUTH_HEADERS,
        )
    assert resp.status_code == 502
    assert resp.json()["errorType"] == "no_metrics_source"


@pytest.mark.asyncio
async def test_relay_timeout_returns_504(client: FastAPI, monkeypatch) -> None:
    async def fake_relay_query(session, org_id, query, kind="instant", params=None, timeout=None):
        raise cluster_relay.RelayTimeoutError("the cluster agent did not answer within 20s")

    monkeypatch.setattr(cluster_relay, "relay_query", fake_relay_query)

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get(
            "/internal/relay/prometheus/query_range",
            params={"org_id": str(TEST_ORG_ID), "query": "up", "start": "0", "end": "1", "step": "15s"},
            headers=AUTH_HEADERS,
        )
    assert resp.status_code == 504
    assert resp.json()["errorType"] == "timeout"


@pytest.mark.asyncio
async def test_successful_prometheus_query_returns_upstream_envelope(client: FastAPI, monkeypatch) -> None:
    envelope = {"status": "success", "data": {"resultType": "vector", "result": []}}
    mock_relay = AsyncMock(return_value=envelope)
    monkeypatch.setattr(cluster_relay, "relay_query", mock_relay)

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get(
            "/internal/relay/prometheus/query",
            params={"org_id": str(TEST_ORG_ID), "query": "up"},
            headers=AUTH_HEADERS,
        )
    assert resp.status_code == 200
    assert resp.json() == envelope
    mock_relay.assert_awaited_once()
    assert mock_relay.call_args.args[1] == TEST_ORG_ID
    assert mock_relay.call_args.args[2] == "up"
    assert mock_relay.call_args.args[3] == "instant"


@pytest.mark.asyncio
async def test_loki_query_range_passes_logql_kind_and_params(client: FastAPI, monkeypatch) -> None:
    envelope = {"status": "success", "data": {"resultType": "streams", "result": []}}
    mock_relay = AsyncMock(return_value=envelope)
    monkeypatch.setattr(cluster_relay, "relay_query", mock_relay)

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get(
            "/internal/relay/loki/query_range",
            params={
                "org_id": str(TEST_ORG_ID), "query": '{app="orders"}',
                "start": "0", "end": "100", "limit": 25, "direction": "backward",
            },
            headers=AUTH_HEADERS,
        )
    assert resp.status_code == 200
    assert resp.json() == envelope
    call_args = mock_relay.call_args.args
    assert call_args[2] == '{app="orders"}'
    assert call_args[3] == "logql"
    assert call_args[4] == {"start": "0", "end": "100", "limit": 25, "direction": "backward"}
