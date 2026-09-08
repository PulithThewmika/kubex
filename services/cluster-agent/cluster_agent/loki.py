"""Loki discovery and LogQL relay (#840).

Mirrors prometheus.py: discovers the in-cluster Loki Service (see
k8s.find_loki) and queries it via its in-cluster DNS name.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from . import k8s

logger = logging.getLogger("kubex.cluster_agent.loki")

DEFAULT_PORT = 3100

# Same defense-in-depth rationale as prometheus.py's PROM_QUERY_TIMEOUT/
# MAX_PROMQL_LENGTH — the backend is trusted for query content, not for
# how expensive a single query can be against the customer's own Loki.
MAX_LOGQL_LENGTH = 4096

_client: httpx.AsyncClient | None = None
_base_url: str | None = None


class QueryTooLongError(Exception):
    pass


def _client_for(base_url: str) -> httpx.AsyncClient:
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
        found = await k8s.find_loki()
    except k8s.RBACDeniedError:
        logger.warning("RBAC denied listing Services — cannot discover Loki")
        return {"status": "rbac_denied", "namespace": None, "service_name": None}
    except Exception:
        logger.exception("Unexpected error discovering Loki")
        return {"status": "error", "namespace": None, "service_name": None}

    if found is None:
        return {"status": "not_found", "namespace": None, "service_name": None}

    namespace, service_name = found
    return {"status": "found", "namespace": namespace, "service_name": service_name}


def in_cluster_url(namespace: str, service_name: str) -> str:
    return f"http://{service_name}.{namespace}.svc.cluster.local:{DEFAULT_PORT}"


async def query_range(base_url: str, logql: str, start: str, end: str, limit: int = 1000, direction: str = "forward") -> dict:
    """Execute a LogQL range query and return Loki's raw JSON response
    body, unmodified — same convention as prometheus.query()."""
    if len(logql) > MAX_LOGQL_LENGTH:
        raise QueryTooLongError(f"LogQL string exceeds {MAX_LOGQL_LENGTH} chars ({len(logql)})")
    client = _client_for(base_url)
    resp = await client.get(
        "/loki/api/v1/query_range",
        params={"query": logql, "start": start, "end": end, "limit": limit, "direction": direction},
    )
    resp.raise_for_status()
    return resp.json()
