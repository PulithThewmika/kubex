"""Real-PostgreSQL lifecycle test for cluster connect/heartbeat/disconnect
(E22-T1-S12).

Mock-based tests (test_api_clusters.py, test_cluster_monitor.py) already
cover each endpoint's logic in isolation. What they can't reproduce is
the actual race the task calls out: the disconnect sweep and a fresh
heartbeat landing concurrently on the same row. Both are single-row
UPDATEs guarded by a WHERE clause re-evaluated under Postgres's row
lock, so whichever commits second sees the other's write and the two
orderings converge on the same correct state — this test drives both
orderings against a real connection to prove that holds, not just that
each one works alone.

Connection modes (tried in order), same convention as
test_dora_integration.py / test_resolve_service_race_integration.py:
1. DORA_TEST_DATABASE_URL env var
2. testcontainers-python (throwaway container)
3. Skip
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone

import bcrypt
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, AsyncSession

try:
    import psycopg2

    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

try:
    from testcontainers.postgres import PostgresContainer

    HAS_TESTCONTAINERS = True
except ImportError:
    HAS_TESTCONTAINERS = False

DORA_TEST_DATABASE_URL = os.environ.get("DORA_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(not HAS_PSYCOPG2, reason="psycopg2 not installed")


def _strip_driver(url: str) -> str:
    return "postgresql://" + url.split("://", 1)[1]


def _as_asyncpg_url(url: str) -> str:
    return "postgresql+asyncpg://" + url.split("://", 1)[1]


@pytest.fixture
def pg() -> AsyncGenerator[tuple[str, str], None]:
    """Yield (asyncpg SQLAlchemy URL, schema name) with a real clusters
    table matching the Cluster model's mapped columns."""
    container = None

    if DORA_TEST_DATABASE_URL:
        psycopg2_url = DORA_TEST_DATABASE_URL
    elif HAS_TESTCONTAINERS:
        try:
            container = PostgresContainer("postgres:16-alpine")
            container.start()
            psycopg2_url = container.get_connection_url()
        except Exception:
            pytest.skip("Docker not available — skipping integration tests")
    else:
        pytest.skip("No database available (set DORA_TEST_DATABASE_URL or install testcontainers)")

    conn = psycopg2.connect(_strip_driver(psycopg2_url))
    conn.autocommit = True
    cur = conn.cursor()

    schema = "test_cluster_lifecycle"
    cur.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
    cur.execute(f"CREATE SCHEMA {schema}")
    cur.execute(f"SET search_path TO {schema}")

    cur.execute("""
        CREATE TABLE clusters (
            id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id               UUID NOT NULL,
            name                 TEXT NOT NULL,
            token_hash           TEXT NOT NULL,
            token_hash_old       TEXT,
            token_old_expires_at TIMESTAMPTZ,
            agent_version        TEXT,
            argocd_version       TEXT,
            argocd_status        TEXT,
            prometheus_status    TEXT,
            last_heartbeat       TIMESTAMPTZ,
            status               TEXT NOT NULL DEFAULT 'pending',
            created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    yield _as_asyncpg_url(psycopg2_url), schema

    cur.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
    cur.close()
    conn.close()
    if container:
        container.stop()


def _engine_and_sessions(asyncpg_url: str, schema: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(asyncpg_url, connect_args={"server_settings": {"search_path": schema}})
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_create_verify_heartbeat_connected_then_three_missed_disconnects(pg: tuple[str, str]) -> None:
    from app.auth import verify_cluster_token
    from app.cluster_monitor import mark_stale_clusters_disconnected
    from app.models.cluster import Cluster

    asyncpg_url, schema = pg
    engine, session_factory = _engine_and_sessions(asyncpg_url, schema)
    org_id = uuid.uuid4()
    token = "kbx_" + "a" * 40
    token_hash = bcrypt.hashpw(token.encode(), bcrypt.gensalt()).decode()

    # create
    async with session_factory() as session:
        cluster = Cluster(org_id=org_id, name="prod", token_hash=token_hash)
        session.add(cluster)
        await session.commit()
        cluster_id = cluster.id

    # verify
    async with session_factory() as session:
        verified = await verify_cluster_token(authorization=f"Bearer {token}", session=session)
        assert verified.id == cluster_id
        assert verified.status == "pending"  # verify alone doesn't flip status

    # heartbeat -> connected
    async with session_factory() as session:
        cluster = (await session.get(Cluster, cluster_id))
        cluster.status = "connected"
        cluster.last_heartbeat = datetime.now(timezone.utc)
        await session.commit()

    async with session_factory() as session:
        cluster = await session.get(Cluster, cluster_id)
        assert cluster.status == "connected"

    # simulate 3+ minutes of missed heartbeats
    async with session_factory() as session:
        cluster = await session.get(Cluster, cluster_id)
        cluster.last_heartbeat = datetime.now(timezone.utc) - timedelta(minutes=4)
        await session.commit()

    async with session_factory() as session:
        count = await mark_stale_clusters_disconnected(session)
    assert count == 1

    async with session_factory() as session:
        cluster = await session.get(Cluster, cluster_id)
        assert cluster.status == "disconnected"

    await engine.dispose()


async def _seed_stale_connected_cluster(
    session_factory: async_sessionmaker[AsyncSession], org_id: uuid.UUID
) -> uuid.UUID:
    from app.models.cluster import Cluster

    async with session_factory() as session:
        cluster = Cluster(
            org_id=org_id,
            name="prod",
            token_hash="x",
            status="connected",
            last_heartbeat=datetime.now(timezone.utc) - timedelta(minutes=4),
        )
        session.add(cluster)
        await session.commit()
        return cluster.id


@pytest.mark.asyncio
async def test_heartbeat_holds_lock_sweep_blocks_then_sees_no_match(pg: tuple[str, str]) -> None:
    """Real concurrency, not just sequential ordering: heartbeat's UPDATE
    takes the row lock and stays uncommitted while the sweep's UPDATE is
    fired concurrently on a second connection. The sweep must block on
    the lock (proven by asserting it hasn't finished yet), then — once
    heartbeat commits — re-evaluate its WHERE clause under Postgres's
    read-committed EvalPlanQual against the now-fresh last_heartbeat and
    find no match."""
    from app.cluster_monitor import mark_stale_clusters_disconnected
    from app.models.cluster import Cluster

    asyncpg_url, schema = pg
    engine, session_factory = _engine_and_sessions(asyncpg_url, schema)
    org_id = uuid.uuid4()
    cluster_id = await _seed_stale_connected_cluster(session_factory, org_id)

    async def run_sweep() -> int:
        async with session_factory() as sweep_session:
            return await mark_stale_clusters_disconnected(sweep_session)

    async with session_factory() as hb_session:
        cluster = await hb_session.get(Cluster, cluster_id)
        cluster.status = "connected"
        cluster.last_heartbeat = datetime.now(timezone.utc)
        await hb_session.flush()  # UPDATE sent, row lock held, not yet committed

        sweep_task = asyncio.create_task(run_sweep())
        await asyncio.sleep(0.3)
        assert not sweep_task.done(), "sweep should still be blocked behind heartbeat's uncommitted row lock"

        await hb_session.commit()  # releases the lock; sweep's UPDATE can now proceed

    sweep_count = await sweep_task
    assert sweep_count == 0

    async with session_factory() as session:
        cluster = await session.get(Cluster, cluster_id)
        assert cluster.status == "connected"

    await engine.dispose()


@pytest.mark.asyncio
async def test_sweep_holds_lock_heartbeat_blocks_then_reconnects(pg: tuple[str, str]) -> None:
    """The other ordering, also driven with real concurrency: sweep takes
    the row lock first and stays uncommitted while a heartbeat is fired
    concurrently on a second connection (proven blocked, same as above).
    Once sweep commits (flipping the row to disconnected), the heartbeat
    proceeds and unconditionally sets status='connected' — so the final
    state is the same as the other ordering."""
    from app.models.cluster import Cluster
    from sqlalchemy import update

    asyncpg_url, schema = pg
    engine, session_factory = _engine_and_sessions(asyncpg_url, schema)
    org_id = uuid.uuid4()
    cluster_id = await _seed_stale_connected_cluster(session_factory, org_id)

    async def run_heartbeat() -> None:
        # Same Core-UPDATE shape as app.routers.clusters.cluster_heartbeat
        # (not ORM attribute assignment) — see that function's comment for
        # why: ORM dirty-tracking would drop status="connected" from the
        # UPDATE if this session's loaded value already matched it.
        async with session_factory() as hb_session:
            await hb_session.execute(
                update(Cluster)
                .where(Cluster.id == cluster_id)
                .values(status="connected", last_heartbeat=datetime.now(timezone.utc))
            )
            await hb_session.commit()

    async with session_factory() as sweep_session:
        # Drive the UPDATE by hand (rather than mark_stale_clusters_disconnected,
        # which also commits) so the lock stays held until we choose to release it.
        from sqlalchemy import update

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=3)
        await sweep_session.execute(
            update(Cluster)
            .where(Cluster.status == "connected", Cluster.last_heartbeat < cutoff)
            .values(status="disconnected")
        )

        hb_task = asyncio.create_task(run_heartbeat())
        await asyncio.sleep(0.3)
        assert not hb_task.done(), "heartbeat should still be blocked behind sweep's uncommitted row lock"

        await sweep_session.commit()  # releases the lock; heartbeat's UPDATE can now proceed

    await hb_task

    async with session_factory() as session:
        cluster = await session.get(Cluster, cluster_id)
        assert cluster.status == "connected"

    await engine.dispose()
