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
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import verify_grafana_datasource_token
from ..db import get_session
from ..models.cluster import Cluster
from ..models.cluster_query import ClusterQuery

logger = logging.getLogger("kubex.ingest.prom")

router = APIRouter(prefix="/api/prom", tags=["prom"], dependencies=[Depends(verify_grafana_datasource_token)])

RELAY_TIMEOUT = float(os.environ.get("PROM_RELAY_TIMEOUT_SECONDS", "20"))
_POLL_INTERVAL = 0.5

# ponytail: regex extraction of the org_id matcher, not a real PromQL
# parser — fine for the dashboard-generated queries that reach this path;
# revisit if arbitrary user PromQL is ever relayed.
_ORG_MATCHER = re.compile(r'\borg_id\s*=\s*"([0-9a-fA-F-]{36})"')


def _error(errtype: str, message: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"status": "error", "errorType": errtype, "error": message},
    )


def _extract_org(query: str) -> tuple[str | None, str]:
    m = _ORG_MATCHER.search(query)
    if not m:
        return None, query
    cleaned = _ORG_MATCHER.sub("", query, count=1)
    # tidy the separators around the hole we just left
    cleaned = re.sub(r",\s*,", ",", cleaned)  # a, , b -> a, b
    cleaned = re.sub(r"\{\s*,\s*", "{", cleaned)  # {, x -> {x
    cleaned = re.sub(r"\s*,\s*\}", "}", cleaned)  # x , } -> x}
    cleaned = re.sub(r"\{\s+\}", "{}", cleaned)  # {  } -> {}
    cleaned = re.sub(r"\s{2,}", " ", cleaned)  # collapse the gap left behind
    return m.group(1), cleaned


async def _relay(session: AsyncSession, raw_query: str, kind: str, params: dict) -> JSONResponse:
    org_str, promql = _extract_org(raw_query)
    if org_str is None:
        return _error("bad_data", "query is missing the org_id label matcher")
    try:
        org_id = uuid.UUID(org_str)
    except ValueError:
        return _error("bad_data", "malformed org_id")

    cluster_id = await session.scalar(
        select(Cluster.id)
        .where(Cluster.org_id == org_id, Cluster.status == "connected")
        .order_by(Cluster.last_heartbeat.desc().nullslast())
        .limit(1)
    )
    if cluster_id is None:
        return _error("no_metrics_source", "org has no connected cluster", status_code=502)

    query_id = await session.scalar(
        pg_insert(ClusterQuery)
        .values(cluster_id=cluster_id, promql=promql, kind=kind, params=params or None)
        .returning(ClusterQuery.id)
    )
    await session.commit()

    deadline = time.monotonic() + RELAY_TIMEOUT
    # Postgres READ COMMITTED: each fresh SELECT sees the agent's committed
    # write to this row without needing our own commit in between.
    while time.monotonic() < deadline:
        await _sleep(_POLL_INTERVAL)
        row = (
            await session.execute(
                select(ClusterQuery.status, ClusterQuery.result).where(ClusterQuery.id == query_id)
            )
        ).first()
        if row is not None and row.status == "completed":
            return JSONResponse(content=row.result)

    logger.warning("relay timeout for cluster %s after %.0fs (query_id=%s)", cluster_id, RELAY_TIMEOUT, query_id)
    return _error(
        "timeout",
        f"the cluster agent did not answer within {RELAY_TIMEOUT:.0f}s — check the agent is connected",
        status_code=504,
    )


# indirection kept so tests can monkeypatch the wait without patching asyncio
async def _sleep(seconds: float) -> None:
    await asyncio.sleep(seconds)


@router.get("/api/v1/query")
async def instant_query(
    query: str,
    time: str | None = None,  # noqa: A002 — Prometheus's own param name
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    return await _relay(session, query, "instant", {"time": time} if time else {})


@router.get("/api/v1/query_range")
async def range_query(
    query: str,
    start: str,
    end: str,
    step: str,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    return await _relay(session, query, "range", {"start": start, "end": end, "step": step})


@router.get("/api/v1/status/buildinfo")
async def buildinfo() -> JSONResponse:
    # Grafana's datasource "Save & Test" and feature-probing hit this.
    return JSONResponse(content={"status": "success", "data": {"version": "2.51.0", "features": {}}})


@router.get("/api/v1/metadata")
async def metadata() -> JSONResponse:
    return JSONResponse(content={"status": "success", "data": {}})
