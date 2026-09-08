"""Internal org-scoped telemetry relay for the MCP server (#840).

The MCP server (a separate Node process/container) has no direct access
to the `cluster_queries` relay ingest and the agent share over Postgres —
it needs an HTTP hop. This router is that hop, authenticated with the
same shared MCP_INTERNAL_TOKEN ingest already uses when calling *out* to
the MCP server (mcp_client.py), reused in the reverse direction.

Unlike routers/prom.py (#832, Grafana's datasource endpoint), the org_id
here is an explicit query parameter, not embedded in the query text —
every caller of this endpoint already has a real org_id in hand (from an
X-Org-Id header already validated upstream), so there's no need for
prom.py's regex-based extraction hack.

Response shape mirrors prom.py's: on success, the upstream Prometheus/Loki
JSON envelope verbatim; on failure, an explicit error envelope
(`{"status": "error", "errorType": ..., "error": ...}`) with a status code
that distinguishes *why* — 502 for no connected cluster, 504 for a relay
timeout — never an empty 200 result. An empty result is indistinguishable
from genuinely no data, which is exactly the ambiguity (Prometheus
unreachable vs. low traffic) this project has already been bitten by once;
a caller here must be able to tell "no data" from "couldn't ask".
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from .. import cluster_relay
from ..auth import verify_internal_token
from ..db import get_session

logger = logging.getLogger("kubex.ingest.relay_internal")

router = APIRouter(
    prefix="/internal/relay", tags=["relay-internal"], dependencies=[Depends(verify_internal_token)]
)


def _error(errtype: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"status": "error", "errorType": errtype, "error": message},
    )


async def _handle(
    session: AsyncSession, org_id_str: str, query: str, kind: str, params: dict[str, Any]
) -> JSONResponse:
    try:
        org_id = uuid.UUID(org_id_str)
    except ValueError:
        return _error("bad_data", "malformed org_id", 400)

    try:
        result = await cluster_relay.relay_query(session, org_id, query, kind, params)
    except cluster_relay.NoClusterError:
        return _error("no_metrics_source", "org has no connected cluster", 502)
    except cluster_relay.RelayTimeoutError as e:
        return _error("timeout", str(e), 504)

    return JSONResponse(content=result)


@router.get("/prometheus/query")
async def prometheus_instant_query(
    org_id: str,
    query: str,
    time: str | None = None,  # noqa: A002 — Prometheus's own param name
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    return await _handle(session, org_id, query, "instant", {"time": time} if time else {})


@router.get("/prometheus/query_range")
async def prometheus_range_query(
    org_id: str,
    query: str,
    start: str,
    end: str,
    step: str,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    return await _handle(session, org_id, query, "range", {"start": start, "end": end, "step": step})


@router.get("/loki/query_range")
async def loki_range_query(
    org_id: str,
    query: str,
    start: str,
    end: str,
    limit: int = 1000,
    direction: str = "forward",
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    return await _handle(
        session,
        org_id,
        query,
        "logql",
        {"start": start, "end": end, "limit": limit, "direction": direction},
    )
