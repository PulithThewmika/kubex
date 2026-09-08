"""Relay client for the org-scoped cluster_queries bridge (#840).

The agent already holds its own direct Postgres connection (get_session,
same DB ingest and the cluster-agent share) — no HTTP hop needed, unlike
the MCP server. Raw SQL, matching this module's existing style (run.py,
reconciliation.py use text() throughout; no ORM models here for
clusters/cluster_queries).

ponytail: near-identical to ingest/app/cluster_relay.py — duplicated
because agent and ingest are separate Python codebases/containers with no
shared package. Two implementations of ~40 lines of polling logic, kept
manually in sync; not worth introducing a shared internal package for.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("kubex.agent.cluster_relay")

DEFAULT_RELAY_TIMEOUT = 20.0
_POLL_INTERVAL = 0.5


class RelayError(Exception):
    """Base class for a relay query that could not be answered."""


class RelayTimeoutError(RelayError):
    """A cluster was queued but its agent never posted a result in time."""


async def queue_and_wait(
    session: AsyncSession,
    cluster_id: uuid.UUID,
    query: str,
    kind: str = "instant",
    params: dict[str, Any] | None = None,
    timeout: float = DEFAULT_RELAY_TIMEOUT,
) -> dict:
    """Queue one query into cluster_queries and block until the cluster
    agent posts a result, or raise RelayTimeoutError.

    Distinct from ingest's version in one way: this already has cluster_id
    in hand (the caller resolved it via the deployment's own join over
    services/clusters — see run.py), so there's no resolve_cluster_for_org
    step here.
    """
    import json

    row = (
        await session.execute(
            text(
                "INSERT INTO cluster_queries (cluster_id, promql, kind, params) "
                "VALUES (:cluster_id, :query, :kind, CAST(:params AS jsonb)) "
                "RETURNING id"
            ),
            {
                "cluster_id": cluster_id,
                "query": query,
                "kind": kind,
                "params": json.dumps(params) if params else None,
            },
        )
    ).first()
    query_id = row.id
    await session.commit()

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        await asyncio.sleep(_POLL_INTERVAL)
        result_row = (
            await session.execute(
                text("SELECT status, result FROM cluster_queries WHERE id = :id"),
                {"id": query_id},
            )
        ).first()
        if result_row is not None and result_row.status == "completed":
            return result_row.result

    logger.warning(
        "relay timeout for cluster %s after %.0fs (query_id=%s, kind=%s)",
        cluster_id, timeout, query_id, kind,
    )
    raise RelayTimeoutError(
        f"the cluster agent did not answer within {timeout:.0f}s — check the agent is connected"
    )
