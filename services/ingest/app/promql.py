"""Prometheus query helpers, routed through the org-scoped cluster relay (#840).

Previously opened an httpx client directly against a hardcoded PROM_URL.
That was wrong for every org except whichever one happens to be running
against the operator's own local Kind cluster: a customer's metrics only
ever exist behind *their own* cluster-agent relay (EPIC-022), and PROM_URL
pointed at the operator's Prometheus regardless of which org's deployment
was actually being scored — so a connected customer cluster's safety-score
cluster-utilization factor and the /compare endpoint's metrics were both
silently reading the wrong cluster's numbers, not just missing data.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from . import cluster_relay

logger = logging.getLogger("kubex.ingest.promql")

OBSERVATION_WINDOW = os.environ.get("OBSERVATION_WINDOW", "15m")
BASELINE_WINDOW = os.environ.get("BASELINE_WINDOW", "30m")

# The cluster-utilization factor is computed synchronously inside the
# GitHub webhook handler (see safety_score.py's own comment on why), which
# must respond well inside GitHub's webhook delivery timeout. The general
# cluster_relay.DEFAULT_RELAY_TIMEOUT (20s, tuned for a Grafana panel load
# or an agent's async tick — see #832/#840) would blow that budget on its
# own before GitHub's ~10s limit is even reached.
SAFETY_SCORE_RELAY_TIMEOUT_SECONDS = float(os.environ.get("SAFETY_SCORE_RELAY_TIMEOUT_SECONDS", "4"))

_UNSAFE_LABEL_RE = re.compile(r'[\\"\n\r]')


def _sanitize_label(value: str) -> str:
    """Escape characters that break PromQL label matchers."""
    return _UNSAFE_LABEL_RE.sub(lambda m: "\\" + m.group(0), value)


def _parse_scalar(envelope: dict) -> float | None:
    """Extract a single scalar from a Prometheus /api/v1/query response
    envelope. Returns None for a legitimately empty result or a NaN —
    the caller can't distinguish that from a relay failure by this return
    value alone, which is why callers that need to (fetch_cluster_utilization)
    catch cluster_relay.RelayError separately instead of relying on this."""
    if envelope.get("status") != "success":
        return None
    results = envelope.get("data", {}).get("result", [])
    if not results:
        return None
    try:
        value = float(results[0]["value"][1])
    except (KeyError, IndexError, ValueError):
        return None
    if value != value:  # NaN check
        return None
    return value


async def _query(
    session: AsyncSession, org_id: uuid.UUID, promql: str, time: datetime, *, timeout: float | None = None
) -> float | None:
    try:
        envelope = await cluster_relay.relay_query(
            session, org_id, promql, "instant", {"time": time.timestamp()}, timeout=timeout
        )
    except cluster_relay.RelayError as e:
        logger.warning("Relay query failed for org %s: %s", org_id, e)
        return None
    return _parse_scalar(envelope)


async def fetch_metrics_at(
    session: AsyncSession, org_id: uuid.UUID, service: str, namespace: str, window: str, timestamp: datetime,
) -> dict[str, float | None]:
    svc, ns = _sanitize_label(service), _sanitize_label(namespace)
    error_rate = await _query(
        session, org_id,
        f'sum(rate(http_requests_total{{service="{svc}",'
        f'namespace="{ns}",status=~"5.."}}[{window}]))'
        f' / '
        f'sum(rate(http_requests_total{{service="{svc}",'
        f'namespace="{ns}"}}[{window}]))',
        timestamp,
    )

    latency_raw = await _query(
        session, org_id,
        f'histogram_quantile(0.99,'
        f'sum(rate(http_request_duration_seconds_bucket{{service="{svc}",'
        f'namespace="{ns}"}}[{window}])) by (le))',
        timestamp,
    )
    latency_p99_ms = latency_raw * 1000 if latency_raw is not None else None

    restarts = await _query(
        session, org_id,
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
    session: AsyncSession, org_id: uuid.UUID, timestamp: datetime,
) -> dict[str, float | bool | None]:
    """Cluster-wide CPU/memory utilization percentage, from node_exporter.

    Used by the safety score's "cluster is under load" risk factor — this
    is intentionally cluster-wide (not per-service), unlike fetch_metrics_at.

    Run concurrently, not sequentially: this is called synchronously from
    the GitHub webhook handler (safety score is computed on
    workflow_run.requested, not in the agent's async loop), so a slow or
    unreachable relay must not cost two serial timeouts on top of each
    other and risk exceeding GitHub's webhook delivery timeout.

    Returns an explicit `unreachable` flag rather than silently folding a
    relay failure into the same None as "genuinely no data" — the caller
    (safety_score.py) records this in `risk_factors` so a 0-point cluster
    factor because the org has no connected cluster reads differently from
    a 0-point factor because the cluster is simply under 75%/80% load.
    """
    cpu_promql = "100 * (1 - avg(rate(node_cpu_seconds_total{mode=\"idle\"}[5m])))"
    mem_promql = "100 * (1 - avg(node_memory_MemAvailable_bytes) / avg(node_memory_MemTotal_bytes))"
    try:
        cpu_envelope, mem_envelope = await asyncio.gather(
            cluster_relay.relay_query(
                session, org_id, cpu_promql, "instant", {"time": timestamp.timestamp()},
                timeout=SAFETY_SCORE_RELAY_TIMEOUT_SECONDS,
            ),
            cluster_relay.relay_query(
                session, org_id, mem_promql, "instant", {"time": timestamp.timestamp()},
                timeout=SAFETY_SCORE_RELAY_TIMEOUT_SECONDS,
            ),
        )
    except cluster_relay.RelayError as e:
        logger.info("Cluster utilization unreachable for org %s: %s", org_id, e)
        return {"cpu_pct": None, "mem_pct": None, "unreachable": True}

    return {
        "cpu_pct": _parse_scalar(cpu_envelope),
        "mem_pct": _parse_scalar(mem_envelope),
        "unreachable": False,
    }
