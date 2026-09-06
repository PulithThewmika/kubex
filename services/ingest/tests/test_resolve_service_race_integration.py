"""Real-PostgreSQL race test for resolve_service's auto-registration
recovery path (CodeRabbit, 2nd round on PR #796).

A mock can't reproduce the actual SQLAlchemy behavior at stake here: on
IntegrityError inside a savepoint, the pending Service object is already
evicted back to the transient state by the rollback, so a manual
session.expunge(service) afterward raises InvalidRequestError instead of
letting the recovery SELECT run. Only a real session against a real
constraint exercises that.

Connection modes (tried in order), same convention as
test_dora_integration.py / test_deployments_notify_idempotency_integration.py:
1. DORA_TEST_DATABASE_URL env var — direct connection to any PostgreSQL
2. testcontainers-python — spins up a temporary PostgreSQL container
3. Skip — if neither is available
"""

from __future__ import annotations

import os
import uuid

import pytest

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
    """postgresql+psycopg2://... -> postgresql://... — psycopg2.connect()
    doesn't understand the +driver dialect suffix SQLAlchemy URLs use."""
    return "postgresql://" + url.split("://", 1)[1]


def _as_asyncpg_url(url: str) -> str:
    """Normalize any postgresql[+driver]:// URL to postgresql+asyncpg://."""
    return "postgresql+asyncpg://" + url.split("://", 1)[1]


@pytest.fixture
def pg():
    """Yield (asyncpg SQLAlchemy URL, schema name) for a real, freshly
    schema'd PostgreSQL instance with the exact services table/constraint
    resolve_service depends on."""
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

    schema = "test_resolve_service_race"
    cur.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
    cur.execute(f"CREATE SCHEMA {schema}")
    cur.execute(f"SET search_path TO {schema}")

    # Full column set the Service model maps — select(Service) selects
    # every mapped column, so a minimal subset 500s with UndefinedColumn.
    cur.execute("""
        CREATE TABLE services (
            id SERIAL PRIMARY KEY,
            org_id UUID NOT NULL,
            name TEXT NOT NULL,
            repo TEXT,
            argocd_app TEXT,
            namespace TEXT NOT NULL DEFAULT 'default',
            prom_components TEXT[],
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_services_org_name UNIQUE (org_id, name)
        );
    """)

    yield _as_asyncpg_url(psycopg2_url), schema

    cur.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
    cur.close()
    conn.close()
    if container:
        container.stop()


@pytest.mark.asyncio
async def test_concurrent_first_time_registration_does_not_crash(pg, caplog):
    """asyncio.gather() alone doesn't reliably reproduce this race — the
    SELECT-then-INSERT window inside resolve_service is too fast for two
    real asyncpg round trips to reliably interleave, even behind a
    barrier that only synchronizes the *start* of each call (verified:
    it doesn't in practice). So drive the race deterministically instead:
    intercept session A's first statement (the pre-insert name lookup)
    and, before returning control to resolve_service, have session B run
    and commit a full competing registration on a separate connection.
    By the time session A reaches its own INSERT, B's row already exists,
    forcing the exact IntegrityError recovery path for real."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.correlation.engine import resolve_service

    asyncpg_url, schema = pg
    # asyncpg-specific way to set search_path per-connection — a URL query
    # string "options=-csearch_path=..." is a libpq/psycopg2 convention
    # that asyncpg doesn't parse the same way.
    engine = create_async_engine(asyncpg_url, connect_args={"server_settings": {"search_path": schema}})
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    org_id = uuid.uuid4()

    winner_id = None

    async with session_factory() as session_a:
        original_execute = session_a.execute
        injected = False

        async def execute_with_injected_race(stmt, *args, **kwargs):
            nonlocal injected, winner_id
            result = await original_execute(stmt, *args, **kwargs)
            if not injected:
                injected = True
                async with session_factory() as session_b:
                    winner_id, _ = await resolve_service(session_b, org_id=org_id, name="orders")
                    await session_b.commit()
            return result

        session_a.execute = execute_with_injected_race

        with caplog.at_level("INFO", logger="kubex.correlation"):
            service_id_a, org_id_a = await resolve_service(session_a, org_id=org_id, name="orders")
            await session_a.commit()

    assert injected, "expected session A's first execute() to trigger the injected competing registration"
    assert any("Lost service auto-registration race" in r.message for r in caplog.records), (
        "expected session A to take the IntegrityError recovery path, not just get lucky"
    )
    assert service_id_a == winner_id
    assert org_id_a == org_id

    async with session_factory() as session:
        from sqlalchemy import text
        count = (await session.execute(text("SELECT count(*) FROM services WHERE org_id = :o"), {"o": org_id})).scalar_one()

    await engine.dispose()

    assert count == 1
