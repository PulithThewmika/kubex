from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from cluster_agent import k8s, prometheus


@pytest.mark.asyncio
async def test_discover_not_found() -> None:
    with patch("cluster_agent.k8s.find_prometheus", AsyncMock(return_value=None)):
        result = await prometheus.discover()
    assert result == {"status": "not_found", "namespace": None, "service_name": None}


@pytest.mark.asyncio
async def test_discover_found() -> None:
    with patch("cluster_agent.k8s.find_prometheus", AsyncMock(return_value=("monitoring", "prometheus-operated"))):
        result = await prometheus.discover()
    assert result == {"status": "found", "namespace": "monitoring", "service_name": "prometheus-operated"}


@pytest.mark.asyncio
async def test_discover_rbac_denied() -> None:
    with patch("cluster_agent.k8s.find_prometheus", AsyncMock(side_effect=k8s.RBACDeniedError("nope"))):
        result = await prometheus.discover()
    assert result["status"] == "rbac_denied"


@pytest.mark.asyncio
async def test_discover_reports_error_on_non_rbac_k8s_failure() -> None:
    with patch("cluster_agent.k8s.find_prometheus", AsyncMock(side_effect=RuntimeError("500 from apiserver"))):
        result = await prometheus.discover()
    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_client_for_closes_previous_client_on_url_change() -> None:
    # Bug found in review, E22-T3: switching base URLs used to replace
    # _client without closing the old one, leaking its connection pool.
    first = prometheus._client_for("http://prom-a.test")
    second = prometheus._client_for("http://prom-b.test")
    assert second is not first
    await asyncio.sleep(0)  # let the scheduled close of `first` run
    assert first.is_closed
    await prometheus.close_client()


def test_in_cluster_url() -> None:
    assert prometheus.in_cluster_url("monitoring", "prometheus-operated") == (
        "http://prometheus-operated.monitoring.svc.cluster.local:9090"
    )


@pytest.mark.asyncio
async def test_query_returns_raw_response_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["query"] == 'up{service="frontend"}'
        assert request.url.params["timeout"] == prometheus.PROM_QUERY_TIMEOUT
        return httpx.Response(200, json={"status": "success", "data": {"result": []}})

    prometheus._client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://prom.test")
    prometheus._base_url = "http://prom.test"
    result = await prometheus.query("http://prom.test", 'up{service="frontend"}')
    assert result == {"status": "success", "data": {"result": []}}
    await prometheus.close_client()


@pytest.mark.asyncio
async def test_query_rejects_oversized_promql_without_hitting_prometheus() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should never reach Prometheus")

    prometheus._client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://prom.test")
    prometheus._base_url = "http://prom.test"
    with pytest.raises(prometheus.QueryTooLongError):
        await prometheus.query("http://prom.test", "up" * (prometheus.MAX_PROMQL_LENGTH))
    await prometheus.close_client()


@pytest.mark.asyncio
async def test_query_range_returns_raw_response_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/query_range"
        assert request.url.params["query"] == 'up{service="frontend"}'
        assert request.url.params["start"] == "0"
        assert request.url.params["end"] == "100"
        assert request.url.params["step"] == "15s"
        return httpx.Response(200, json={"status": "success", "data": {"resultType": "matrix", "result": []}})

    prometheus._client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://prom.test")
    prometheus._base_url = "http://prom.test"
    result = await prometheus.query_range("http://prom.test", 'up{service="frontend"}', "0", "100", "15s")
    assert result == {"status": "success", "data": {"resultType": "matrix", "result": []}}
    await prometheus.close_client()


@pytest.mark.asyncio
async def test_query_range_rejects_oversized_promql_without_hitting_prometheus() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should never reach Prometheus")

    prometheus._client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://prom.test")
    prometheus._base_url = "http://prom.test"
    with pytest.raises(prometheus.QueryTooLongError):
        await prometheus.query_range("http://prom.test", "up" * (prometheus.MAX_PROMQL_LENGTH), "0", "1", "15s")
    await prometheus.close_client()
