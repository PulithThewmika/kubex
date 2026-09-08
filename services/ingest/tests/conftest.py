import hashlib
import hmac
import os
import uuid
from unittest.mock import DEFAULT, AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("GITHUB_APP_WEBHOOK_SECRET", "test-app-secret")
os.environ.setdefault("ARGOCD_WEBHOOK_TOKEN", "test-token")
os.environ.setdefault("ALERTMANAGER_WEBHOOK_TOKEN", "test-am-token")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-at-least-32-bytes-long")
os.environ.setdefault("MCP_INTERNAL_TOKEN", "test-internal-token")

# Several integration tests (test_org_isolation.py, test_dora_integration.py
# and its siblings, test_auth_github_oauth.py) accept a "real Postgres" env
# var (*_TEST_DATABASE_URL) whose fixture teardown TRUNCATEs tables CASCADE.
# A prior session pointed one of these at the live dev database and wiped
# real org/deployment history with no backup (see CLAUDE.md's memory:
# feedback-test-db-safety). Now that #817 moved the platform DB to
# Supabase, refuse ANY such var pointed at a Supabase host, at collection
# time, so a mistake in one test file can't slip past this file — this is
# the one place every test run passes through.
for _name, _value in os.environ.items():
    _value_lower = (_value or "").lower()
    if _name.endswith("_TEST_DATABASE_URL") and _value and (
        "supabase.co" in _value_lower or "supabase.com" in _value_lower
    ):
        raise RuntimeError(
            f"{_name} points at a Supabase host — its fixture teardown runs "
            "TRUNCATE ... CASCADE and must never run against the shared "
            "platform database. Point it at a disposable Postgres instance "
            "you started yourself, or unset it to fall back to testcontainers."
        )

from app.main import app  # noqa: E402
from app.db import get_session  # noqa: E402
from app.auth_middleware import UserContext, get_current_user  # noqa: E402

TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
TEST_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


@pytest.fixture(autouse=True)
def _no_real_safety_score_network_calls():
    """compute_safety_score's cluster-utilization factor makes a real
    Prometheus HTTP call. Webhook-level tests exercise the correlation/
    idempotency logic, not the safety score formula itself (see
    test_safety_score.py) — stub it out so tests stay fast and
    deterministic regardless of what's listening on PROM_URL locally."""
    with patch(
        "app.routers.webhooks_github.compute_safety_score",
        AsyncMock(return_value=(0, {})),
    ):
        yield


def _sign_payload(payload: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


class _FakeNestedTransaction:
    """Minimal stand-in for SQLAlchemy's AsyncSessionTransaction: an async
    context manager, never suppresses exceptions (matching real savepoint
    semantics — session.begin_nested() itself is a plain sync call that
    returns this, not a coroutine)."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _default_mock_execute(stmt, params=None):
    """Route organizations lookups to TEST_ORG_ID; leave everything else to
    the mock's normal return_value (returning DEFAULT keeps that in effect).

    resolve_service/resolve_org_id fall back to a default-org query
    (SELECT ... FROM organizations ...) whenever nothing else matches, so
    that query must resolve to a real id or get_default_org_id raises.
    Tests that set `mock_session.execute.return_value = ...` directly
    (most API-route tests) are unaffected, since DEFAULT defers to it.
    """
    if "organizations" in str(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = TEST_ORG_ID
        return result
    if "token_hash" in str(stmt):
        # find_cluster_by_token's bcrypt-walk (select(Cluster)) — matched on
        # "token_hash" rather than "clusters" since several raw-SQL API
        # queries LEFT JOIN clusters without selecting that column, and a
        # bare "clusters" substring match would swallow those too. Empty by
        # default so the legacy-token webhook tests (which never register a
        # cluster) fall through to "no per-cluster match" instead of
        # iterating a MagicMock. Tests that need an actual cluster match
        # set mock_session.execute.return_value/side_effect directly.
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        return result
    return DEFAULT


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=_default_mock_execute,
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
    )
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.begin_nested = MagicMock(return_value=_FakeNestedTransaction())
    return session


@pytest.fixture
def client(mock_session):
    async def override_get_session():
        yield mock_session

    async def override_get_current_user() -> UserContext:
        return UserContext(user_id=TEST_USER_ID, org_id=TEST_ORG_ID)

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_user] = override_get_current_user
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def github_secret():
    return os.environ["GITHUB_WEBHOOK_SECRET"]


@pytest.fixture
def argocd_token():
    return os.environ["ARGOCD_WEBHOOK_TOKEN"]


@pytest.fixture
def alertmanager_token():
    return os.environ["ALERTMANAGER_WEBHOOK_TOKEN"]


@pytest.fixture
def sign_github_payload(github_secret):
    def _sign(payload: bytes) -> str:
        return _sign_payload(payload, github_secret)
    return _sign


@pytest.fixture
def github_app_secret():
    return os.environ["GITHUB_APP_WEBHOOK_SECRET"]


@pytest.fixture
def sign_github_app_payload(github_app_secret):
    def _sign(payload: bytes) -> str:
        return _sign_payload(payload, github_app_secret)
    return _sign
