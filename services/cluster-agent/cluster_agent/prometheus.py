"""Prometheus discovery and PromQL relay (E22-T3-S6/S8).

Discovery finds the in-cluster Service (kube-prometheus-stack names it
"prometheus-operated"; other common installs use "prometheus-server" or
"prometheus-k8s" — see k8s.find_prometheus) and queries it via its
in-cluster DNS name, since this agent runs as a Pod inside the same
cluster.
"""

from __future__ import annotations

import logging

import httpx

from . import k8s

logger = logging.getLogger("kubex.cluster_agent.prometheus")

DEFAULT_PORT = 9090

_client: httpx.AsyncClient | None = None
_base_url: str | None = None


def _client_for(base_url: str) -> httpx.AsyncClient:
    global _client, _base_url
    if _client is None or _client.is_closed or _base_url != base_url:
        _client = httpx.AsyncClient(base_url=base_url, timeout=10.0)
        _base_url = base_url
    return _client


async def close_client() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


async def discover() -> dict:
    """Returns {status, namespace, service_name} for the heartbeat payload."""
    try:
        found = await k8s.find_prometheus()
    except k8s.RBACDeniedError:
        logger.warning("RBAC denied listing Services — cannot discover Prometheus")
        return {"status": "rbac_denied", "namespace": None, "service_name": None}

    if found is None:
        return {"status": "not_found", "namespace": None, "service_name": None}

    namespace, service_name = found
    return {"status": "found", "namespace": namespace, "service_name": service_name}


def in_cluster_url(namespace: str, service_name: str) -> str:
    return f"http://{service_name}.{namespace}.svc.cluster.local:{DEFAULT_PORT}"


async def query(base_url: str, promql: str) -> dict:
    """Execute a PromQL instant query and return Prometheus's raw JSON
    response body, unmodified — the ingest side (or whatever consumes
    cluster_queries.result) is expected to know how to read a standard
    /api/v1/query response."""
    client = _client_for(base_url)
    resp = await client.get("/api/v1/query", params={"query": promql})
    resp.raise_for_status()
    return resp.json()
