"""Cluster disconnect sweep (E22-T1-S11).

Heartbeats (app.routers.clusters.cluster_heartbeat) flip a cluster to
'connected' as they arrive; nothing flips it back on its own once they
stop. This sweep runs periodically and marks any cluster whose last
heartbeat is older than DISCONNECT_THRESHOLD as 'disconnected'.

Only rows currently 'connected' are touched — a cluster that has never
sent a heartbeat stays 'pending', which is correct (it was never
connected to begin with).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .models.cluster import Cluster
from .models.cluster_query import ClusterQuery

logger = logging.getLogger("kubex.ingest.cluster_monitor")

DISCONNECT_THRESHOLD = timedelta(minutes=3)
SWEEP_INTERVAL_SECONDS = 30
# /api/prom deletes its own row on timeout and the agent poll skips rows
# older than 60s, but an ingest crash mid-wait can still orphan a row, and
# 'completed' rows the relay read but didn't get to delete pile up. Reap
# anything older than this from either state.
CLUSTER_QUERY_TTL = timedelta(minutes=5)


async def mark_stale_clusters_disconnected(session: AsyncSession) -> int:
    cutoff = datetime.now(timezone.utc) - DISCONNECT_THRESHOLD
    result = await session.execute(
        update(Cluster)
        .where(Cluster.status == "connected", Cluster.last_heartbeat < cutoff)
        .values(status="disconnected")
    )
    await session.commit()
    if result.rowcount:
        logger.info("Marked %d cluster(s) disconnected (no heartbeat since %s)", result.rowcount, cutoff)
    return result.rowcount


async def reap_stale_cluster_queries(session: AsyncSession) -> int:
    cutoff = datetime.now(timezone.utc) - CLUSTER_QUERY_TTL
    result = await session.execute(
        delete(ClusterQuery).where(ClusterQuery.requested_at < cutoff)
    )
    await session.commit()
    if result.rowcount:
        logger.info("Reaped %d stale cluster_queries row(s) older than %s", result.rowcount, cutoff)
    return result.rowcount


async def run_disconnect_sweep_loop(async_session_factory: async_sessionmaker[AsyncSession]) -> None:
    # ponytail: plain polling loop, no APScheduler dep in this service —
    # fine at this project's scale; upgrade if a second periodic ingest
    # job appears and shared scheduling machinery earns its keep.
    while True:
        await asyncio.sleep(SWEEP_INTERVAL_SECONDS)
        try:
            async with async_session_factory() as session:
                await mark_stale_clusters_disconnected(session)
                await reap_stale_cluster_queries(session)
        except Exception:
            logger.exception("Cluster disconnect sweep failed")
