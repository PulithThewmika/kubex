"""Cross-org data isolation — the acceptance test for E20-T2 / EPIC-020 (#600).

Seeds two real organizations, each with its own service, deployment, and
alert, against a real PostgreSQL instance with the full migration set
applied, then hits every org-scoped endpoint as org A's user and asserts
none of org B's data is visible or reachable — matching test_dora_integration.py
and test_auth_github_oauth.py's real-Postgres pattern, since mocks can't
catch a missing WHERE org_id = ... clause.

Connection modes (tried in order):
1. ORG_ISOLATION_TEST_DATABASE_URL env var — direct connection to any PostgreSQL
2. testcontainers-python — spins up a temporary PostgreSQL container
3. Skip — if neither is available
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

try:
    from testcontainers.postgres import PostgresContainer
    HAS_TESTCONTAINERS = True
except ImportError:
    HAS_TESTCONTAINERS = False

ORG_ISOLATION_TEST_DATABASE_URL = os.environ.get("ORG_ISOLATION_TEST_DATABASE_URL")
# Refused at collection time if pointed at Supabase — see conftest.py's
# generic *_TEST_DATABASE_URL guard (this fixture's teardown TRUNCATEs
# CASCADE; see CLAUDE.md's memory: feedback-test-db-safety).

pytestmark = pytest.mark.skipif(
    not (ORG_ISOLATION_TEST_DATABASE_URL or HAS_TESTCONTAINERS),
    reason="No database available (set ORG_ISOLATION_TEST_DATABASE_URL or install testcontainers)",
)


@pytest.fixture(scope="module")
def pg_url():
    """Spin up (or connect to) a real Postgres and apply every migration."""
    container = None
    if ORG_ISOLATION_TEST_DATABASE_URL:
        raw_url = ORG_ISOLATION_TEST_DATABASE_URL
    else:
        try:
            container = PostgresContainer("postgres:16-alpine")
            container.start()
            raw_url = container.get_connection_url()
        except Exception:
            pytest.skip("Docker not available — skipping integration tests")

    try:
        import psycopg2

        sync_url = raw_url.replace("+psycopg2", "")
        conn = psycopg2.connect(sync_url)
        conn.autocommit = True
        cur = conn.cursor()

        migrations_dir = os.path.join(os.path.dirname(__file__), "..", "migrations")
        sql_files = sorted(f for f in os.listdir(migrations_dir) if f.startswith("V") and f.endswith(".sql"))
        for fname in sql_files:
            with open(os.path.join(migrations_dir, fname)) as f:
                cur.execute(f.read())

        cur.close()
        conn.close()

        yield sync_url.replace("postgresql://", "postgresql+asyncpg://")
    finally:
        if container:
            container.stop()


@pytest.fixture
async def pg_session(pg_url):
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(pg_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()
    async with engine.begin() as conn:
        from sqlalchemy import text
        await conn.execute(text(
            "TRUNCATE alerts, health_assessments, deployments, services, organizations RESTART IDENTITY CASCADE"
        ))
    await engine.dispose()


async def _seed_org(pg_session, *, org_name: str, service_name: str):
    from app.models.alert import Alert
    from app.models.deployment import Deployment
    from app.models.organization import Organization
    from app.models.service import Service

    org = Organization(name=org_name, slug=org_name)
    pg_session.add(org)
    await pg_session.flush()

    service = Service(org_id=org.id, name=service_name, repo=f"acme/{service_name}")
    pg_session.add(service)
    await pg_session.flush()

    now = datetime.now(timezone.utc)
    deployment = Deployment(
        org_id=org.id,
        service_id=service.id,
        commit_sha="abc1234",
        status="deployed",
        commit_at=now,
        finished_at=now,
    )
    pg_session.add(deployment)
    await pg_session.flush()

    alert = Alert(
        org_id=org.id,
        deployment_id=deployment.id,
        service_id=service.id,
        severity="critical",
        title="error rate spike",
        fired_at=now,
        resolved_at=now,
    )
    pg_session.add(alert)
    await pg_session.flush()

    return {
        "org_id": org.id,
        "service_id": service.id,
        "service_name": service_name,
        "deployment_id": deployment.id,
        "alert_id": alert.id,
    }


@pytest.mark.asyncio
async def test_cross_org_isolation_across_all_endpoints(pg_url, pg_session):
    org_a = await _seed_org(pg_session, org_name="org-a", service_name="org-a-service")
    org_b = await _seed_org(pg_session, org_name="org-b", service_name="org-b-service")
    await pg_session.commit()

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.auth_middleware import UserContext, get_current_user
    from app.db import get_session
    from app.main import app

    engine = create_async_engine(pg_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_session():
        async with async_session() as session:
            yield session

    async def override_get_current_user():
        return UserContext(user_id=uuid.uuid4(), org_id=org_a["org_id"])

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/api/services")
            assert resp.status_code == 200
            names = [s["name"] for s in resp.json()]
            assert org_a["service_name"] in names
            assert org_b["service_name"] not in names

            resp = await ac.get("/api/deployments")
            assert resp.status_code == 200
            ids = [d["id"] for d in resp.json()]
            assert org_a["deployment_id"] in ids
            assert org_b["deployment_id"] not in ids

            resp = await ac.get(f"/api/deployments/{org_b['deployment_id']}")
            assert resp.status_code == 404

            resp = await ac.get(f"/api/deployments/{org_b['deployment_id']}/health")
            assert resp.status_code == 404

            resp = await ac.get(f"/api/deployments/{org_a['deployment_id']}")
            assert resp.status_code == 200

            resp = await ac.get("/api/alerts")
            assert resp.status_code == 200
            alert_ids = [a["id"] for a in resp.json()]
            assert org_a["alert_id"] in alert_ids
            assert org_b["alert_id"] not in alert_ids

            resp = await ac.get("/api/dora", params={"service": org_b["service_name"]})
            assert resp.status_code == 200
            data = resp.json()
            assert not data["deploy_frequency_per_day"]
            assert data["mttr_s"] is None

            resp = await ac.get("/api/dora", params={"service": org_a["service_name"]})
            assert resp.status_code == 200
            data = resp.json()
            assert data["deploy_frequency_per_day"]

            resp = await ac.get(
                "/api/compare",
                params={"a": org_b["deployment_id"], "b": org_a["deployment_id"]},
            )
            assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()
