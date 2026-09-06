"""Integration test for V021's real unique index on deployments(commit_sha,
service_id) (E21-T3-S6) — mock-based tests can assert the SQL shape of the
ON CONFLICT clause, but only a real PostgreSQL instance proves the index
itself rejects/upserts duplicates instead of silently allowing them.

Connection modes (tried in order), same convention as test_dora_integration.py:
1. DORA_TEST_DATABASE_URL env var — direct connection to any PostgreSQL
2. testcontainers-python — spins up a temporary PostgreSQL container
3. Skip — if neither is available
"""

from __future__ import annotations

import os

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


@pytest.fixture(scope="module")
def pg():
    container = None

    if DORA_TEST_DATABASE_URL:
        conn = psycopg2.connect(DORA_TEST_DATABASE_URL)
    elif HAS_TESTCONTAINERS:
        try:
            container = PostgresContainer("postgres:16-alpine")
            container.start()
            conn = psycopg2.connect(container.get_connection_url())
        except Exception:
            pytest.skip("Docker not available — skipping integration tests")
    else:
        pytest.skip("No database available (set DORA_TEST_DATABASE_URL or install testcontainers)")

    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE services (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE
        );
    """)
    cur.execute("""
        CREATE TABLE deployments (
            id SERIAL PRIMARY KEY,
            service_id INTEGER NOT NULL REFERENCES services(id),
            commit_sha TEXT,
            workflow_run_id BIGINT,
            status TEXT NOT NULL DEFAULT 'pending',
            finished_at TIMESTAMPTZ
        );
    """)
    # The exact index V021 adds — scoped to workflow_run_id IS NULL so it
    # never collides with rows process_workflow_run creates/upserts on
    # workflow_run_id (e.g. a manual GitHub Actions re-run of the same
    # commit gets a new workflow_run_id but the same commit_sha).
    cur.execute("""
        CREATE UNIQUE INDEX uq_deployments_commit_service
            ON deployments (commit_sha, service_id)
            WHERE commit_sha IS NOT NULL AND workflow_run_id IS NULL;
    """)
    cur.execute("INSERT INTO services (name) VALUES ('orders') RETURNING id")
    service_id = cur.fetchone()[0]

    yield conn, service_id

    cur.close()
    conn.close()
    if container:
        container.stop()


@pytest.fixture(autouse=True)
def _clean_deployments(pg):
    conn, _ = pg
    cur = conn.cursor()
    cur.execute("TRUNCATE deployments RESTART IDENTITY CASCADE")
    conn.commit()
    yield
    cur.close()


def test_plain_duplicate_insert_violates_the_index(pg):
    conn, service_id = pg
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO deployments (service_id, commit_sha, status) VALUES (%s, %s, 'syncing')",
        (service_id, "abc1234"),
    )
    with pytest.raises(psycopg2.errors.UniqueViolation):
        cur.execute(
            "INSERT INTO deployments (service_id, commit_sha, status) VALUES (%s, %s, 'syncing')",
            (service_id, "abc1234"),
        )
    conn.rollback()


def test_on_conflict_upsert_produces_exactly_one_row(pg):
    """The pattern used by POST /api/deployments/notify's orphan branch —
    ON CONFLICT (commit_sha, service_id) DO UPDATE — must converge on a
    single row across repeated deliveries instead of erroring or
    duplicating."""
    conn, service_id = pg
    cur = conn.cursor()

    for status in ("syncing", "syncing", "deployed"):
        cur.execute(
            """
            INSERT INTO deployments (service_id, commit_sha, status)
            VALUES (%s, %s, %s)
            ON CONFLICT (commit_sha, service_id) WHERE commit_sha IS NOT NULL
            DO UPDATE SET status = EXCLUDED.status
            """,
            (service_id, "def5678", status),
        )
    conn.commit()

    cur.execute("SELECT count(*), max(status) FROM deployments WHERE commit_sha = 'def5678'")
    count, final_status = cur.fetchone()
    assert count == 1
    assert final_status == "deployed"


def test_workflow_run_rows_are_exempt_from_the_index(pg):
    """A row carrying workflow_run_id (created by webhooks_github.py's
    process_workflow_run, which upserts on workflow_run_id instead) must
    not collide with an orphan row sharing the same commit_sha — e.g. a
    manual GitHub Actions re-run assigns a new workflow_run_id to the same
    commit (/code-review high on PR #796)."""
    conn, service_id = pg
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO deployments (service_id, commit_sha, workflow_run_id) VALUES (%s, %s, 111)",
        (service_id, "ghi9012"),
    )
    cur.execute(
        "INSERT INTO deployments (service_id, commit_sha, workflow_run_id) VALUES (%s, %s, 222)",
        (service_id, "ghi9012"),
    )
    conn.commit()

    cur.execute("SELECT count(*) FROM deployments WHERE commit_sha = 'ghi9012'")
    assert cur.fetchone()[0] == 2


def test_null_commit_sha_is_exempt_from_uniqueness(pg):
    """The index is partial (WHERE commit_sha IS NOT NULL) — rows with no
    commit_sha (not yet correlated) must not collide with each other."""
    conn, service_id = pg
    cur = conn.cursor()
    cur.execute("INSERT INTO deployments (service_id, commit_sha) VALUES (%s, NULL)", (service_id,))
    cur.execute("INSERT INTO deployments (service_id, commit_sha) VALUES (%s, NULL)", (service_id,))
    conn.commit()

    cur.execute("SELECT count(*) FROM deployments WHERE commit_sha IS NULL")
    assert cur.fetchone()[0] == 2
