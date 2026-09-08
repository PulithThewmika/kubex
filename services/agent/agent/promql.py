"""PromQL query builders and Prometheus HTTP client.

Constructs and executes PromQL queries for each health metric using the
@ modifier for instant evaluation at a specific timestamp. Query set
follows doc 05 exactly.

Two execution paths (#840): a legacy/local service (no cluster_id - the
in-cluster Kind deployment wired directly to PROM_URL) queries Prometheus
directly, unchanged from before. A service on a remote customer cluster
(cluster_id set, EPIC-022) routes through the cluster_queries relay
instead - PROM_URL is the *operator's own* Prometheus and was never a
meaningful source for a customer's metrics; querying it regardless of
cluster_id (the previous behavior) meant health scores for connected
customer clusters were silently computed against the wrong Prometheus
entirely, not just missing data.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from . import cluster_relay
from .config import PROM_URL

logger = logging.getLogger("kubex.agent.promql")

# Raised by _execute when the relay path (cluster_id set) fails to get an
# answer in time. Distinct from a plain None so callers can tell
# "unreachable" apart from "queried fine, no data" - re-exported under a
# clearer name for this module's callers (health_score.py) rather than
# making them import cluster_relay directly.
MetricsUnreachableError = cluster_relay.RelayTimeoutError

_UNSAFE_LABEL_RE = re.compile(r'[\\"\n\r]')


def _sanitize_label(value: str) -> str:
    """Escape characters that break PromQL label matchers."""
    return _UNSAFE_LABEL_RE.sub(lambda m: "\\" + m.group(0), value)


_client: httpx.AsyncClient | None = None


def get_prom_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(base_url=PROM_URL, timeout=10.0)
    return _client


async def close_prom_client() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        _client = None


def _parse_envelope(data: dict) -> float | None:
    if data.get("status") != "success":
        logger.warning("Prometheus query failed: %s", data)
        return None
    results = data.get("data", {}).get("result", [])
    if not results:
        return None
    try:
        value = float(results[0]["value"][1])
    except (KeyError, IndexError, ValueError) as e:
        logger.warning("Failed to parse Prometheus response: %s", e)
        return None
    if value != value:  # NaN check
        return None
    return value


async def query_prometheus(promql: str, time: datetime) -> float | None:
    """Execute a PromQL instant query directly against PROM_URL.

    Uses /api/v1/query with the `time` parameter for point-in-time evaluation.
    Returns the scalar float result, or None if no data / error.
    """
    client = get_prom_client()
    ts = time.timestamp()
    try:
        resp = await client.get(
            "/api/v1/query",
            params={"query": promql, "time": ts},
        )
        resp.raise_for_status()
        return _parse_envelope(resp.json())
    except httpx.HTTPStatusError as e:
        logger.warning("Prometheus HTTP error: %s - %s", e.response.status_code, promql)
        return None
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        logger.warning("Prometheus unreachable: %s", e)
        return None
    except (KeyError, IndexError, ValueError) as e:
        logger.warning("Failed to parse Prometheus response for %s: %s", promql, e)
        return None


async def _execute(
    promql: str, timestamp: datetime, *, session: AsyncSession | None = None, cluster_id: uuid.UUID | None = None,
) -> float | None:
    """Dispatch to the relay (remote customer cluster) or PROM_URL (local/
    legacy) depending on whether a cluster_id was passed. Raises
    MetricsUnreachableError instead of returning None on a relay timeout -
    the caller must not silently fold "couldn't ask" into "no data".

    Every real caller (health_score.py, reconciliation.py) always has a
    session in scope and passes it unconditionally — cluster_id alone
    decides legacy vs. relay (None = legacy/local, set = a connected
    remote cluster). So cluster_id set without a session is the only
    combination that can never be a legitimate call (there is no way to
    relay without a session) — raise loudly rather than silently falling
    through to the direct-PROM_URL path, which would otherwise reproduce
    the exact "queried the operator's own Prometheus instead of the
    customer's relay" bug this module exists to eliminate."""
    if cluster_id is not None and session is None:
        raise ValueError("cluster_id was given without a session — cannot relay")
    if session is not None and cluster_id is not None:
        envelope = await cluster_relay.queue_and_wait(
            session, cluster_id, promql, "instant", {"time": timestamp.timestamp()},
        )
        return _parse_envelope(envelope)
    return await query_prometheus(promql, timestamp)


async def query_error_rate(
    service: str, namespace: str, window: str, timestamp: datetime,
    *, session: AsyncSession | None = None, cluster_id: uuid.UUID | None = None,
) -> float | None:
    """Query HTTP error rate (5xx / total) for a service over a window."""
    svc, ns = _sanitize_label(service), _sanitize_label(namespace)
    promql = (
        f'sum(rate(http_requests_total{{service="{svc}",'
        f'namespace="{ns}",status=~"5.."}}[{window}]))'
        f' / '
        f'sum(rate(http_requests_total{{service="{svc}",'
        f'namespace="{ns}"}}[{window}]))'
    )
    return await _execute(promql, timestamp, session=session, cluster_id=cluster_id)


async def query_latency_p99(
    service: str, namespace: str, window: str, timestamp: datetime,
    *, session: AsyncSession | None = None, cluster_id: uuid.UUID | None = None,
) -> float | None:
    """Query p99 latency in seconds for a service over a window."""
    svc, ns = _sanitize_label(service), _sanitize_label(namespace)
    promql = (
        f'histogram_quantile(0.99,'
        f'sum(rate(http_request_duration_seconds_bucket{{service="{svc}",'
        f'namespace="{ns}"}}[{window}])) by (le))'
    )
    result = await _execute(promql, timestamp, session=session, cluster_id=cluster_id)
    if result is not None:
        return result * 1000  # convert to milliseconds
    return None


async def query_restarts(
    service: str, namespace: str, window: str, timestamp: datetime,
    *, session: AsyncSession | None = None, cluster_id: uuid.UUID | None = None,
) -> float | None:
    """Query container restart count increase over a window."""
    svc, ns = _sanitize_label(service), _sanitize_label(namespace)
    promql = (
        f'sum(increase(kube_pod_container_status_restarts_total'
        f'{{namespace="{ns}",container="{svc}"}}[{window}]))'
    )
    return await _execute(promql, timestamp, session=session, cluster_id=cluster_id)


async def query_request_rate(
    service: str, namespace: str, window: str, timestamp: datetime,
    *, session: AsyncSession | None = None, cluster_id: uuid.UUID | None = None,
) -> float | None:
    """Query request rate (rps) for guard-rail volume check."""
    svc, ns = _sanitize_label(service), _sanitize_label(namespace)
    promql = (
        f'sum(rate(http_requests_total{{service="{svc}",'
        f'namespace="{ns}"}}[{window}]))'
    )
    return await _execute(promql, timestamp, session=session, cluster_id=cluster_id)


async def query_cpu(
    service: str, namespace: str, window: str, timestamp: datetime,
    *, session: AsyncSession | None = None, cluster_id: uuid.UUID | None = None,
) -> float | None:
    """Query CPU usage for a service (stretch - safety score)."""
    svc, ns = _sanitize_label(service), _sanitize_label(namespace)
    promql = (
        f'sum(rate(container_cpu_usage_seconds_total'
        f'{{namespace="{ns}",container="{svc}"}}[{window}]))'
    )
    return await _execute(promql, timestamp, session=session, cluster_id=cluster_id)


async def query_memory(
    service: str, namespace: str, window: str, timestamp: datetime,
    *, session: AsyncSession | None = None, cluster_id: uuid.UUID | None = None,
) -> float | None:
    """Query memory usage in bytes for a service (stretch - safety score)."""
    svc, ns = _sanitize_label(service), _sanitize_label(namespace)
    promql = (
        f'sum(container_memory_working_set_bytes'
        f'{{namespace="{ns}",container="{svc}"}})'
    )
    return await _execute(promql, timestamp, session=session, cluster_id=cluster_id)
