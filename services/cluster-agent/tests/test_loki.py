from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from cluster_agent import k8s, loki


@pytest.mark.asyncio
async def test_discover_not_found() -> None:
    with patch("cluster_agent.k8s.find_loki", AsyncMock(return_value=None)):
        result = await loki.discover()
    assert result == {"status": "not_found", "namespace": None, "service_name": None}


@pytest.mark.asyncio
async def test_discover_found() -> None:
    with patch("cluster_agent.k8s.find_loki", AsyncMock(return_value=("monitoring", "loki"))):
        result = await loki.discover()
    assert result == {"status": "found", "namespace": "monitoring", "service_name": "loki"}


@pytest.mark.asyncio
async def test_discover_rbac_denied() -> None:
    with patch("cluster_agent.k8s.find_loki", AsyncMock(side_effect=k8s.RBACDeniedError("nope"))):
        result = await loki.discover()
    assert result["status"] == "rbac_denied"


@pytest.mark.asyncio
async def test_discover_reports_error_on_non_rbac_k8s_failure() -> None:
    with patch("cluster_agent.k8s.find_loki", AsyncMock(side_effect=RuntimeError("500 from apiserver"))):
        result = await loki.discover()
    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_client_for_closes_previous_client_on_url_change() -> None:
    first = loki._client_for("http://loki-a.test")
    second = loki._client_for("http://loki-b.test")
    assert second is not first
    await asyncio.sleep(0)  # let the scheduled close of `first` run
    assert first.is_closed
    await loki.close_client()


def test_in_cluster_url() -> None:
    assert loki.in_cluster_url("monitoring", "loki") == (
        "http://loki.monitoring.svc.cluster.local:3100"
    )


@pytest.mark.asyncio
async def test_query_range_returns_raw_response_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["query"] == '{app="orders"}'
        assert request.url.params["start"] == "1700000000"
        assert request.url.params["end"] == "1700000100"
        assert request.url.params["limit"] == "50"
        assert request.url.params["direction"] == "backward"
        return httpx.Response(200, json={"status": "success", "data": {"result": []}})

    loki._client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://loki.test")
    loki._base_url = "http://loki.test"
    result = await loki.query_range("http://loki.test", '{app="orders"}', "1700000000", "1700000100", 50, "backward")
    assert result == {"status": "success", "data": {"result": []}}
    await loki.close_client()


@pytest.mark.asyncio
async def test_query_range_rejects_oversized_logql_without_hitting_loki() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should never reach Loki")

    loki._client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://loki.test")
    loki._base_url = "http://loki.test"
    with pytest.raises(loki.QueryTooLongError):
        await loki.query_range("http://loki.test", "x" * (loki.MAX_LOGQL_LENGTH + 1), "0", "1")
    await loki.close_client()
