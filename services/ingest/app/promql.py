"""Prometheus query helpers, routed through the org-scoped cluster relay (#840).

Two execution paths, mirroring agent/promql.py exactly: a legacy/local
service (no cluster_id - the in-cluster Kind demo wired directly to
PROM_URL) queries Prometheus directly, unchanged from before this PR. A
service on a remote customer cluster (cluster_id set, EPIC-022) routes
through the cluster_queries relay instead - PROM_URL is the operator's
own Prometheus and was never a meaningful source for a customer's
metrics; querying it regardless of cluster_id would mean the safety
score's cluster-utilization factor and the /compare endpoint silently
read the wrong cluster's numbers for any org with a connected remote
cluster, not just missing data.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import uuid
from datetime import datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from . import cluster_relay

logger = logging.getLogger("kubex.ingest.promql")

PROM_URL = os.environ.get("PROM_URL", "http://localhost:9090")
OBSERVATION_WINDOW = os.environ.get("OBSERVATION_WINDOW", "15m")
BASELINE_WINDOW = os.environ.get("BASELINE_WINDOW", "30m")

# The cluster-utilization factor is computed synchronously inside the
# GitHub webhook handler (see safety_score.py's own comment on why), which
# must respond well inside GitHub's webhook delivery timeout. The general
# cluster_relay.DEFAULT_RELAY_TIMEOUT (20s, tuned for a Grafana panel load
# or an async agent tick) would blow that budget on its own before
# GitHub's ~10s limit is even reached.
SAFETY_SCORE_RELAY_TIMEOUT_SECONDS = float(os.environ.get("SAFETY_SCORE_RELAY_TIMEOUT_SECONDS", "4"))

_UNSAFE_LABEL_RE = re.compile(r'[\\"\n\r]')


def _sanitize_label(value: str) -> str:
    """Escape characters that break PromQL label matchers."""
    return _UNSAFE_LABEL_RE.sub(lambda m: "\\" + m.group(0), value)


_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
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
    """Extract a single scalar from a Prometheus /api/v1/query response
    envelope. Returns None for a legitimately empty result or a NaN -
    the caller can't distinguish that from a relay failure by this return
    value alone, which is why callers that need to (fetch_cluster_utilization)
    catch cluster_relay.RelayError separately instead of relying on this."""
    if data.get("status") != "success":
        return None
    results = data.get("data", {}).get("result", [])
    if not results:
        return None
    try:
        value = float(results[0]["value"][1])
    except (KeyError, IndexError, ValueError):
        return None
    if value != value:  # NaN check
        return None
    return value


async def _query_direct(promql: str, time: datetime) -> float | None:
    """Legacy/local path: query PROM_URL directly over HTTP. No DB
    session involved, so concurrent calls (asyncio.gather) are safe."""
    client = _get_client()
    try:
        resp = await client.get(
            "/api/v1/query",
            params={"query": promql, "time": time.timestamp()},
        )
        resp.raise_for_status()
        return _parse_envelope(resp.json())
    except (httpx.HTTPError, KeyError, IndexError, ValueError):
        return None


async def _query(
    session: AsyncSession, cluster_id: uuid.UUID | None, promql: str, time: datetime,
    *, timeout: float | None = None,
) -> float | None:
    if cluster_id is None:
        return await _query_direct(promql, time)
    try:
        envelope = await cluster_relay.queue_and_wait(
            session, cluster_id, promql, "instant", {"time": time.timestamp()}, timeout=timeout,
        )
    except cluster_relay.RelayError as e:
        logger.warning("Relay query failed for cluster %s: %s", cluster_id, e)
        return None
    return _parse_envelope(envelope)


async def fetch_metrics_at(
    session: AsyncSession, cluster_id: uuid.UUID | None, service: str, namespace: str,
    window: str, timestamp: datetime,
) -> dict[str, float | None]:
    svc, ns = _sanitize_label(service), _sanitize_label(namespace)
    error_rate = await _query(
        session, cluster_id,
        f'sum(rate(http_requests_total{{service="{svc}",'
        f'namespace="{ns}",status=~"5.."}}[{window}]))'
        f' / '
        f'sum(rate(http_requests_total{{service="{svc}",'
        f'namespace="{ns}"}}[{window}]))',
        timestamp,
    )

    latency_raw = await _query(
        session, cluster_id,
        f'histogram_quantile(0.99,'
        f'sum(rate(http_request_duration_seconds_bucket{{service="{svc}",'
        f'namespace="{ns}"}}[{window}])) by (le))',
        timestamp,
    )
    latency_p99_ms = latency_raw * 1000 if latency_raw is not None else None

    restarts = await _query(
        session, cluster_id,
        f'sum(increase(kube_pod_container_status_restarts_total'
        f'{{namespace="{ns}",container="{svc}"}}[{window}]))',
        timestamp,
    )

    return {
        "error_rate": error_rate,
        "latency_p99_ms": latency_p99_ms,
        "restarts": restarts,
    }


async def fetch_cluster_utilization(
    session: AsyncSession, cluster_id: uuid.UUID | None, timestamp: datetime,
) -> dict[str, float | bool | None]:
    """Cluster-wide CPU/memory utilization percentage, from node_exporter.

    Used by the safety score's "cluster is under load" risk factor - this
    is intentionally cluster-wide (not per-service), unlike fetch_metrics_at.

    Returns an explicit `unreachable` flag rather than silently folding a
    relay failure into the same None as "genuinely no data" - the caller
    (safety_score.py) records this in `risk_factors` so a 0-point cluster
    factor because the org has no *connected* cluster reads differently
    from a 0-point factor because the cluster is simply under 75%/80% load.

    The two queries run sequentially on the relay path (not
    asyncio.gather) - both would otherwise call cluster_relay.queue_and_wait
    concurrently on the same AsyncSession, which SQLAlchemy's AsyncSession
    does not support from more than one concurrent task. The legacy direct
    path has no such constraint (a plain httpx client, no shared session)
    and keeps its concurrency.
    """
    cpu_promql = "100 * (1 - avg(rate(node_cpu_seconds_total{mode=\"idle\"}[5m])))"
    mem_promql = "100 * (1 - avg(node_memory_MemAvailable_bytes) / avg(node_memory_MemTotal_bytes))"

    if cluster_id is None:
        cpu_pct, mem_pct = await asyncio.gather(
            _query_direct(cpu_promql, timestamp),
            _query_direct(mem_promql, timestamp),
        )
        return {"cpu_pct": cpu_pct, "mem_pct": mem_pct, "unreachable": False}

    try:
        cpu_envelope = await cluster_relay.queue_and_wait(
            session, cluster_id, cpu_promql, "instant", {"time": timestamp.timestamp()},
            timeout=SAFETY_SCORE_RELAY_TIMEOUT_SECONDS,
        )
        mem_envelope = await cluster_relay.queue_and_wait(
            session, cluster_id, mem_promql, "instant", {"time": timestamp.timestamp()},
            timeout=SAFETY_SCORE_RELAY_TIMEOUT_SECONDS,
        )
    except cluster_relay.RelayError as e:
        logger.info("Cluster utilization unreachable for cluster %s: %s", cluster_id, e)
        return {"cpu_pct": None, "mem_pct": None, "unreachable": True}

    return {
        "cpu_pct": _parse_envelope(cpu_envelope),
        "mem_pct": _parse_envelope(mem_envelope),
        "unreachable": False,
    }
