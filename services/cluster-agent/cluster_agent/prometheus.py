"""Prometheus discovery and PromQL relay (E22-T3-S6/S8).

Discovery finds the in-cluster Service (kube-prometheus-stack names it
"prometheus-operated"; other common installs use "prometheus-server" or
"prometheus-k8s" — see k8s.find_prometheus) and queries it via its
in-cluster DNS name, since this agent runs as a Pod inside the same
cluster.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from . import k8s

logger = logging.getLogger("kubex.cluster_agent.prometheus")

DEFAULT_PORT = 9090

# Defense-in-depth against a buggy or compromised backend forwarding an
# expensive/adversarial query at the customer's own Prometheus — the
# backend is trusted for query *content*, but the agent shouldn't let a
# single query be able to degrade the customer's cluster (security
# review, E22-T3). PROM_QUERY_TIMEOUT is passed as Prometheus's own
# `timeout` param so Prometheus self-aborts, rather than relying only on
# the client socket timeout below.
PROM_QUERY_TIMEOUT = "10s"
MAX_PROMQL_LENGTH = 4096


class QueryTooLongError(Exception):
    pass


_client: httpx.AsyncClient | None = None
_base_url: str | None = None


def _client_for(base_url: str) -> httpx.AsyncClient:
    # Bug found in review, E22-T3: replacing _client on a URL change
    # without closing the old one first leaked its connection pool —
    # close_client() only ever closes whichever client happens to be
    # current at the time it's called.
    global _client, _base_url
    if _client is None or _client.is_closed or _base_url != base_url:
        old_client = _client
        _client = httpx.AsyncClient(base_url=base_url, timeout=10.0)
        _base_url = base_url
        if old_client is not None and not old_client.is_closed:
            asyncio.ensure_future(old_client.aclose())
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
    except Exception:
        logger.exception("Unexpected error discovering Prometheus")
        return {"status": "error", "namespace": None, "service_name": None}

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
    if len(promql) > MAX_PROMQL_LENGTH:
        raise QueryTooLongError(f"PromQL string exceeds {MAX_PROMQL_LENGTH} chars ({len(promql)})")
    client = _client_for(base_url)
    resp = await client.get("/api/v1/query", params={"query": promql, "timeout": PROM_QUERY_TIMEOUT})
    resp.raise_for_status()
    return resp.json()


async def query_range(base_url: str, promql: str, start: str, end: str, step: str) -> dict:
    """Execute a PromQL range query (#840) — needed for the MCP server's
    query_metrics/generate_incident_report tools, which relay
    /api/v1/query_range through ingest's routers/relay_internal.py as a
    "range"-kind cluster_queries row. Returns Prometheus's raw JSON
    response body unmodified, same convention as query()."""
    if len(promql) > MAX_PROMQL_LENGTH:
        raise QueryTooLongError(f"PromQL string exceeds {MAX_PROMQL_LENGTH} chars ({len(promql)})")
    client = _client_for(base_url)
    resp = await client.get(
        "/api/v1/query_range",
        params={"query": promql, "start": start, "end": end, "step": step, "timeout": PROM_QUERY_TIMEOUT},
    )
    resp.raise_for_status()
    return resp.json()
