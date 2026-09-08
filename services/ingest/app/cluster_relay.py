"""Internal relay client for the org-scoped cluster_queries bridge (#840).

Two callers inside ingest go through this one module rather than each
rolling their own resolve-cluster + queue + poll logic: the safety score's
cluster-utilization factor (promql.py, same process, direct call) and the
internal relay HTTP endpoint used by the MCP server (routers/relay_internal.py,
a separate Node process that can only reach this over the network).

ponytail: this duplicates the near-identical ``_relay()`` helper in
routers/prom.py (#832, Grafana's org-scoped datasource endpoint) rather than
refactoring prom.py to call this module. The two were built concurrently by
separate sessions on separate branches, and prom.py's version is coupled to
its Grafana-specific "org_id embedded as a PromQL label matcher" extraction
(_extract_org), which doesn't apply here — this module's callers already
have a real org_id in hand (from a UserContext, an X-Org-Id header, or a
Service row), not a query string to parse it out of. Upgrade path: once both
branches land on dev, refactor prom.py's _relay() to delegate to
resolve_cluster_for_org()/queue_and_wait() here and delete its own copy of
the polling loop.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from .models.cluster import Cluster
from .models.cluster_query import ClusterQuery

logger = logging.getLogger("kubex.ingest.cluster_relay")

# Same default as routers/prom.py's PROM_RELAY_TIMEOUT_SECONDS — tuned for
# a Grafana panel load / an async agent tick, not for a synchronous request
# with a hard deadline. Callers on a tight deadline (the safety score,
# computed inside the GitHub webhook handler) must pass their own shorter
# `timeout` explicitly rather than relying on this default.
DEFAULT_RELAY_TIMEOUT = float(os.environ.get("PROM_RELAY_TIMEOUT_SECONDS", "20"))
_POLL_INTERVAL = 0.5


class RelayError(Exception):
    """Base class for a relay query that could not be answered."""


class NoClusterError(RelayError):
    """The org has no connected cluster to relay the query to."""


class RelayTimeoutError(RelayError):
    """A cluster was queued but its agent never posted a result in time.

    Deliberately a distinct exception from NoClusterError — "no cluster
    connected" and "a cluster is connected but isn't answering" are
    different failure modes a caller may want to report differently, and
    conflating either with "the query legitimately returned no data" is
    exactly the gotcha (Prometheus-unreachable-vs-low-traffic) this
    module exists to avoid reintroducing.
    """


async def resolve_cluster_for_org(session: AsyncSession, org_id: uuid.UUID) -> uuid.UUID:
    """Find the org's most-recently-heartbeated connected cluster.

    Raises NoClusterError rather than returning None — every caller of
    this module needs to handle "no cluster" as an explicit, distinct
    outcome, and a raised exception makes that unmissable at every call
    site instead of an easily-ignored falsy return.
    """
    cluster_id = await session.scalar(
        select(Cluster.id)
        .where(Cluster.org_id == org_id, Cluster.status == "connected")
        .order_by(Cluster.last_heartbeat.desc().nullslast())
        .limit(1)
    )
    if cluster_id is None:
        raise NoClusterError(f"org {org_id} has no connected cluster")
    return cluster_id


async def queue_and_wait(
    session: AsyncSession,
    cluster_id: uuid.UUID,
    query: str,
    kind: str = "instant",
    params: dict[str, Any] | None = None,
    timeout: float | None = None,
) -> dict:
    """Queue one query into cluster_queries and block until the cluster
    agent posts a result, or raise RelayTimeoutError.

    `query` is stored in the table's `promql` column regardless of `kind`
    (a "logql"-kind row's LogQL string lives there too) — matching the
    column cluster-agent's /queries poller already reads, added by #832;
    renaming it to something transport-neutral isn't worth a migration
    for this.
    """
    timeout = DEFAULT_RELAY_TIMEOUT if timeout is None else timeout

    query_id = await session.scalar(
        pg_insert(ClusterQuery)
        .values(cluster_id=cluster_id, promql=query, kind=kind, params=params or None)
        .returning(ClusterQuery.id)
    )
    await session.commit()

    deadline = time.monotonic() + timeout
    # Postgres READ COMMITTED: each fresh SELECT sees the agent's committed
    # write to this row without this session needing a commit in between.
    while time.monotonic() < deadline:
        await asyncio.sleep(_POLL_INTERVAL)
        row = (
            await session.execute(
                select(ClusterQuery.status, ClusterQuery.result).where(ClusterQuery.id == query_id)
            )
        ).first()
        if row is not None and row.status == "completed":
            return row.result

    logger.warning(
        "relay timeout for cluster %s after %.0fs (query_id=%s, kind=%s)",
        cluster_id, timeout, query_id, kind,
    )
    raise RelayTimeoutError(
        f"the cluster agent did not answer within {timeout:.0f}s — check the agent is connected"
    )


async def relay_query(
    session: AsyncSession,
    org_id: uuid.UUID,
    query: str,
    kind: str = "instant",
    params: dict[str, Any] | None = None,
    timeout: float | None = None,
) -> dict:
    """Resolve org -> connected cluster, then queue_and_wait. Raises
    NoClusterError or RelayTimeoutError (both RelayError) on failure."""
    cluster_id = await resolve_cluster_for_org(session, org_id)
    return await queue_and_wait(session, cluster_id, query, kind, params, timeout)
