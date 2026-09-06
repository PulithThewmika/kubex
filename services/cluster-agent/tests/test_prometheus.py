from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from cluster_agent import k8s, prometheus


@pytest.mark.asyncio
async def test_discover_not_found():
    with patch("cluster_agent.k8s.find_prometheus", AsyncMock(return_value=None)):
        result = await prometheus.discover()
    assert result == {"status": "not_found", "namespace": None, "service_name": None}


@pytest.mark.asyncio
async def test_discover_found():
    with patch("cluster_agent.k8s.find_prometheus", AsyncMock(return_value=("monitoring", "prometheus-operated"))):
        result = await prometheus.discover()
    assert result == {"status": "found", "namespace": "monitoring", "service_name": "prometheus-operated"}


@pytest.mark.asyncio
async def test_discover_rbac_denied():
    with patch("cluster_agent.k8s.find_prometheus", AsyncMock(side_effect=k8s.RBACDeniedError("nope"))):
        result = await prometheus.discover()
    assert result["status"] == "rbac_denied"


def test_in_cluster_url():
    assert prometheus.in_cluster_url("monitoring", "prometheus-operated") == (
        "http://prometheus-operated.monitoring.svc.cluster.local:9090"
    )


@pytest.mark.asyncio
async def test_query_returns_raw_response_json():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["query"] == "up"
        return httpx.Response(200, json={"status": "success", "data": {"result": []}})

    prometheus._client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://prom.test")
    prometheus._base_url = "http://prom.test"
    result = await prometheus.query("http://prom.test", "up")
    assert result == {"status": "success", "data": {"result": []}}
    await prometheus.close_client()
