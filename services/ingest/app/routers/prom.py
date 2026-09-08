"""Org-scoped Prometheus-compatible read API (#832).

Grafana's ``kubex-prometheus`` datasource points here instead of at a
Prometheus. Each panel query carries the caller's org as an
``org_id="<uuid>"`` label matcher (injected by the panel proxy from
``UserContext`` — see routers/grafana.py). This endpoint:

1. extracts and strips that matcher (the customer's own Prometheus has no
   such label),
2. resolves the org to its connected cluster,
3. queues the cleaned PromQL into the ``cluster_queries`` relay,
4. blocks up to ``PROM_RELAY_TIMEOUT_SECONDS`` for the cluster agent to
   post a result back, and
5. returns Prometheus's own JSON envelope verbatim.

A timeout or a missing agent returns a Prometheus *error* envelope, never
an empty result set — an empty panel is indistinguishable from genuinely
low traffic (see the health-score gotcha), so the distinction has to be
explicit here.

The DB session is never held across the bounded wait: the insert commits
on its own short-lived session and each poll uses a fresh one, so a slow
agent can't pin a connection from the shared pool (and starve webhook
ingestion) for the whole timeout window.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..auth import verify_grafana_datasource_token
from ..db import async_session
from ..models.cluster import Cluster
from ..models.cluster_query import ClusterQuery

logger = logging.getLogger("kubex.ingest.prom")

router = APIRouter(prefix="/api/prom", tags=["prom"], dependencies=[Depends(verify_grafana_datasource_token)])

RELAY_TIMEOUT = float(os.environ.get("PROM_RELAY_TIMEOUT_SECONDS", "20"))
_POLL_INTERVAL = 0.5
# Mirrors the cluster agent's own cap (cluster_agent/prometheus.MAX_PROMQL_LENGTH)
# — reject here before the regex work + insert + wait rather than after.
_MAX_QUERY_LENGTH = 4096

# ponytail: regex extraction of the org_id matcher, not a real PromQL
# parser — fine for the dashboard-generated queries that reach this path;
# revisit if arbitrary user PromQL is ever relayed.
_ORG_MATCHER = re.compile(r'\borg_id\s*=\s*"([0-9a-fA-F-]{36})"')
# Optional: a multi-cluster org's customer dashboard can pin a panel to a
# specific cluster with a cluster="<uuid>" matcher (#836).
_CLUSTER_MATCHER = re.compile(r'\bcluster\s*=\s*"([0-9a-fA-F-]{36})"')


def _error(errtype: str, message: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"status": "error", "errorType": errtype, "error": message},
    )


def _tidy(query: str) -> str:
    query = re.sub(r",\s*,", ",", query)  # a, , b -> a,b
    query = re.sub(r"\{\s*,\s*", "{", query)  # {, x -> {x
    query = re.sub(r"\s*,\s*\}", "}", query)  # x , } -> x}
    query = re.sub(r"\{\s+\}", "{}", query)  # {  } -> {}
    return re.sub(r"\s{2,}", " ", query)  # collapse the gap left behind


def _extract_org(query: str) -> tuple[str | None, str | None, str | None]:
    """Returns (org_id, cluster_id | None, promql with every org_id/cluster
    matcher stripped). Returns ``(None, None, None)`` if the query names
    more than one distinct org_id (or cluster) — a query that can't be
    unambiguously attributed is rejected, not guessed at."""
    orgs = set(_ORG_MATCHER.findall(query))
    if len(orgs) != 1:
        return (None, None, query) if not orgs else (None, None, None)
    cleaned = _ORG_MATCHER.sub("", query)  # strip all, not just the first
    clusters = set(_CLUSTER_MATCHER.findall(cleaned))
    if len(clusters) > 1:
        return None, None, None
    cleaned = _CLUSTER_MATCHER.sub("", cleaned)
    return orgs.pop(), (clusters.pop() if clusters else None), _tidy(cleaned)


# indirection kept so tests can monkeypatch the wait without patching asyncio
async def _sleep(seconds: float) -> None:
    await asyncio.sleep(seconds)


async def _relay(raw_query: str, kind: str, params: dict) -> JSONResponse:
    if len(raw_query) > _MAX_QUERY_LENGTH:
        return _error("bad_data", f"query exceeds {_MAX_QUERY_LENGTH} chars")

    org_str, cluster_str, promql = _extract_org(raw_query)
    if org_str is None:
        if promql is None:
            return _error("bad_data", "query names more than one org_id or cluster")
        return _error("bad_data", "query is missing the org_id label matcher")
    try:
        org_id = uuid.UUID(org_str)
        pinned = uuid.UUID(cluster_str) if cluster_str else None
    except ValueError:
        return _error("bad_data", "malformed org_id or cluster")

    async with async_session() as session:
        # A pinned cluster still has to belong to the caller's org and be
        # connected; otherwise fall back to the org's newest connected one.
        conditions = [Cluster.org_id == org_id, Cluster.status == "connected"]
        if pinned is not None:
            conditions.append(Cluster.id == pinned)
        cluster_id = await session.scalar(
            select(Cluster.id).where(*conditions).order_by(Cluster.last_heartbeat.desc().nullslast()).limit(1)
        )
        if cluster_id is None:
            detail = (
                "pinned cluster is not a connected cluster of this org"
                if pinned
                else "org has no connected cluster"
            )
            return _error("no_metrics_source", detail, status_code=502)

        query_id = await session.scalar(
            pg_insert(ClusterQuery)
            .values(cluster_id=cluster_id, promql=promql, kind=kind, params=params or None)
            .returning(ClusterQuery.id)
        )
        await session.commit()

    deadline = time.monotonic() + RELAY_TIMEOUT
    # Postgres READ COMMITTED: a fresh SELECT sees the agent's committed
    # write. A new short-lived session per poll so the connection goes
    # back to the pool between iterations.
    while time.monotonic() < deadline:
        await _sleep(_POLL_INTERVAL)
        async with async_session() as session:
            row = (
                await session.execute(
                    select(ClusterQuery.status, ClusterQuery.result).where(ClusterQuery.id == query_id)
                )
            ).first()
            if row is not None and row.status == "completed":
                result = row.result
                await session.execute(delete(ClusterQuery).where(ClusterQuery.id == query_id))
                await session.commit()
                return JSONResponse(content=result)

    # Nobody is waiting on this row any more — drop it so it isn't picked
    # up and run against the customer's Prometheus when the agent recovers,
    # and so the table doesn't grow unbounded during an agent outage.
    async with async_session() as session:
        await session.execute(
            delete(ClusterQuery).where(ClusterQuery.id == query_id, ClusterQuery.status == "pending")
        )
        await session.commit()
    logger.warning("relay timeout for cluster %s after %.0fs (query_id=%s)", cluster_id, RELAY_TIMEOUT, query_id)
    return _error(
        "timeout",
        f"the cluster agent did not answer within {RELAY_TIMEOUT:.0f}s — check the agent is connected",
        status_code=504,
    )


@router.get("/api/v1/query")
async def instant_query(
    query: str,
    time: str | None = None,  # noqa: A002 — Prometheus's own param name
) -> JSONResponse:
    return await _relay(query, "instant", {"time": time} if time else {})


@router.get("/api/v1/query_range")
async def range_query(query: str, start: str, end: str, step: str) -> JSONResponse:
    return await _relay(query, "range", {"start": start, "end": end, "step": step})


@router.get("/api/v1/status/buildinfo")
async def buildinfo() -> JSONResponse:
    # Grafana's datasource "Save & Test" and feature-probing hit this.
    return JSONResponse(content={"status": "success", "data": {"version": "2.51.0", "features": {}}})


@router.get("/api/v1/metadata")
async def metadata() -> JSONResponse:
    return JSONResponse(content={"status": "success", "data": {}})


# The customer dashboards source their template vars from Postgres, not
# from label discovery — but Grafana's metric browser / a future
# Prometheus-typed var would 404 hard without these. Empty is honest: the
# relay is per-query, there's no catalogue to enumerate.
@router.get("/api/v1/labels")
@router.get("/api/v1/series")
async def _empty_list() -> JSONResponse:
    return JSONResponse(content={"status": "success", "data": []})


@router.get("/api/v1/label/{name}/values")
async def _label_values(name: str) -> JSONResponse:  # noqa: ARG001
    return JSONResponse(content={"status": "success", "data": []})
