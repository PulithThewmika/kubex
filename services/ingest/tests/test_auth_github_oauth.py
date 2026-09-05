"""Tests for the GitHub OAuth login flow (#538/#549).

Mock-based tests exercise the router's HTTP-facing behavior (state/nonce
validation, token-exchange error handling, cookie attributes) with the
DB and GitHub API stubbed out. TestUpsertLogic below runs the actual
upsert helpers against a real PostgreSQL instance (V012 schema applied)
since ON CONFLICT / role-assignment semantics are exactly what mocking
would hide bugs in.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from httpx import ASGITransport, AsyncClient, Request, Response

from app.auth import JWT_SECRET, SHELL_URL
from app.routers import auth as auth_router

TEST_NONCE = "test-nonce"


def _make_state(redirect: str = "/", *, nonce: str = TEST_NONCE, exp_delta: timedelta = timedelta(minutes=10)) -> str:
    return jwt.encode(
        {"nonce": nonce, "redirect": redirect, "exp": datetime.now(timezone.utc) + exp_delta},
        JWT_SECRET,
        algorithm="HS256",
    )


# ── GET /auth/github ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_redirects_to_github_authorize(client):
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/auth/github", follow_redirects=False)

    assert resp.status_code in (302, 307)
    # A cached 302 here would replay a stale state/nonce on the next visit
    # to this URL — browsers do cache redirects without this header.
    assert resp.headers["cache-control"] == "no-store"
    location = urlparse(resp.headers["location"])
    assert location.netloc == "github.com"
    assert location.path == "/login/oauth/authorize"
    qs = parse_qs(location.query)
    assert qs["scope"] == ["read:user user:email"]
    assert "state" in qs
    # state is a signed JWT carrying the default redirect target
    claims = jwt.decode(qs["state"][0], JWT_SECRET, algorithms=["HS256"])
    assert claims["redirect"] == "/"

    set_cookie = resp.headers["set-cookie"]
    assert "oauth_nonce=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie
    # Lax, not Strict — this cookie must still be sent back on the
    # top-level GET navigation GitHub redirects the browser through.
    assert "samesite=lax" in set_cookie.lower()
    nonce_cookie_value = set_cookie.split("oauth_nonce=", 1)[1].split(";", 1)[0]
    assert claims["nonce"] == nonce_cookie_value


@pytest.mark.asyncio
async def test_login_preserves_relative_redirect_param(client):
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/auth/github?redirect=/dashboard", follow_redirects=False)

    location = urlparse(resp.headers["location"])
    qs = parse_qs(location.query)
    claims = jwt.decode(qs["state"][0], JWT_SECRET, algorithms=["HS256"])
    assert claims["redirect"] == "/dashboard"


@pytest.mark.asyncio
async def test_login_rejects_absolute_url_redirect(client):
    """An absolute/protocol-relative redirect target would turn this into
    an open redirect — it must fall back to the default instead."""
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/auth/github?redirect=https://evil.example.com", follow_redirects=False)

    location = urlparse(resp.headers["location"])
    qs = parse_qs(location.query)
    claims = jwt.decode(qs["state"][0], JWT_SECRET, algorithms=["HS256"])
    assert claims["redirect"] == "/"


@pytest.mark.asyncio
async def test_login_rejects_protocol_relative_redirect(client):
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/auth/github?redirect=//evil.example.com", follow_redirects=False)

    location = urlparse(resp.headers["location"])
    qs = parse_qs(location.query)
    claims = jwt.decode(qs["state"][0], JWT_SECRET, algorithms=["HS256"])
    assert claims["redirect"] == "/"


@pytest.mark.asyncio
async def test_login_rejects_backslash_redirect(client):
    """Browsers' URL parser normalizes a leading backslash to a forward
    slash, so "/\\evil.com" is interpreted the same as "//evil.com" — a
    plain "//" prefix check alone misses this bypass."""
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/auth/github?redirect=/%5Cevil.example.com", follow_redirects=False)

    location = urlparse(resp.headers["location"])
    qs = parse_qs(location.query)
    claims = jwt.decode(qs["state"][0], JWT_SECRET, algorithms=["HS256"])
    assert claims["redirect"] == "/"


# ── GET /auth/github/callback ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_callback_missing_state_is_422(client):
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/auth/github/callback?code=abc")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_callback_invalid_state_is_401(client):
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/auth/github/callback?code=abc&state=not-a-jwt")
    assert resp.status_code == 401
    assert "state" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_callback_expired_state_is_401(client):
    expired_state = _make_state(exp_delta=timedelta(minutes=-1))
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get(f"/auth/github/callback?code=abc&state={expired_state}", cookies={"oauth_nonce": TEST_NONCE})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_callback_missing_nonce_cookie_is_401(client):
    """No nonce cookie at all — e.g. a third party replaying a captured
    callback URL without ever having visited /auth/github themselves."""
    state = _make_state()
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get(f"/auth/github/callback?code=abc&state={state}")
    assert resp.status_code == 401
    assert "nonce" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_callback_mismatched_nonce_cookie_is_401(client):
    """This is the login-CSRF case: a validly-signed state minted for one
    browser session must not be honored from a different one."""
    state = _make_state(nonce="nonce-from-a-different-browser")
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get(f"/auth/github/callback?code=abc&state={state}", cookies={"oauth_nonce": TEST_NONCE})
    assert resp.status_code == 401
    assert "nonce" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_callback_token_exchange_failure_is_401(client):
    state = _make_state()
    fake_client = AsyncMock()
    fake_client.post.return_value = Response(
        200, json={"error": "bad_verification_code"}, request=Request("POST", "https://github.com/login/oauth/access_token")
    )

    with patch("app.routers.auth._get_client", return_value=fake_client):
        async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
            resp = await ac.get(
                f"/auth/github/callback?code=bad-code&state={state}", cookies={"oauth_nonce": TEST_NONCE}
            )

    assert resp.status_code == 401
    assert "token exchange" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_callback_token_exchange_5xx_is_502(client):
    state = _make_state()
    fake_client = AsyncMock()
    fake_client.post.return_value = Response(
        503, text="upstream unavailable", request=Request("POST", "https://github.com/login/oauth/access_token")
    )

    with patch("app.routers.auth._get_client", return_value=fake_client):
        async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
            resp = await ac.get(
                f"/auth/github/callback?code=bad-code&state={state}", cookies={"oauth_nonce": TEST_NONCE}
            )

    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_callback_profile_fetch_5xx_is_502(client):
    state = _make_state()
    fake_client = AsyncMock()
    fake_client.post.return_value = Response(
        200, json={"access_token": "gho_faketoken"}, request=Request("POST", "https://github.com/login/oauth/access_token")
    )
    fake_client.get.return_value = Response(
        500, text="server error", request=Request("GET", "https://api.github.com/user")
    )

    with patch("app.routers.auth._get_client", return_value=fake_client):
        async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
            resp = await ac.get(
                f"/auth/github/callback?code=good-code&state={state}", cookies={"oauth_nonce": TEST_NONCE}
            )

    assert resp.status_code == 502


def _github_http_client(*, orgs: list[dict], orgs_status: int = 200, emails_status: int = 200) -> AsyncMock:
    fake_client = AsyncMock()
    fake_client.post.return_value = Response(
        200, json={"access_token": "gho_faketoken"}, request=Request("POST", "https://github.com/login/oauth/access_token")
    )

    async def _get(url, headers=None):
        req = Request("GET", url)
        if url.endswith("/user"):
            return Response(200, json={"id": 42, "login": "octocat", "avatar_url": "https://x/a.png"}, request=req)
        if url.endswith("/user/emails"):
            if emails_status != 200:
                return Response(emails_status, text="rate limited", request=req)
            return Response(200, json=[{"email": "octocat@example.com", "primary": True}], request=req)
        if url.endswith("/user/orgs"):
            if orgs_status != 200:
                return Response(orgs_status, text="rate limited", request=req)
            return Response(200, json=orgs, request=req)
        raise AssertionError(f"unexpected GET {url}")

    fake_client.get.side_effect = _get
    return fake_client


@pytest.mark.asyncio
async def test_callback_happy_path_no_orgs_sets_session_cookie(client, mock_session):
    state = _make_state(redirect="/dashboard")
    fake_client = _github_http_client(orgs=[])

    user_result = MagicMock()
    user_result.scalar_one.return_value = "11111111-1111-1111-1111-111111111111"
    mock_session.execute = AsyncMock(return_value=user_result)

    with (
        patch("app.routers.auth._get_client", return_value=fake_client),
        patch("app.routers.auth._upsert_organization", AsyncMock(return_value="22222222-2222-2222-2222-222222222222")) as mock_org,
        patch("app.routers.auth._upsert_membership", AsyncMock(return_value="owner")) as mock_membership,
    ):
        async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
            resp = await ac.get(
                f"/auth/github/callback?code=good-code&state={state}",
                cookies={"oauth_nonce": TEST_NONCE},
                follow_redirects=False,
            )

    assert resp.status_code == 302
    assert resp.headers["location"] == f"{SHELL_URL}/dashboard"
    assert resp.headers["cache-control"] == "no-store"
    mock_org.assert_awaited_once_with(mock_session, github_org_id=None, login="octocat")
    mock_membership.assert_awaited_once_with(
        mock_session, "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"
    )
    mock_session.commit.assert_awaited()

    set_cookie = resp.headers["set-cookie"]
    assert "session=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie
    assert "samesite=strict" in set_cookie.lower()

    cookie_value = set_cookie.split("session=", 1)[1].split(";", 1)[0]
    claims = jwt.decode(cookie_value, JWT_SECRET, algorithms=["HS256"])
    assert claims["user_id"] == "11111111-1111-1111-1111-111111111111"
    assert claims["org_id"] == "22222222-2222-2222-2222-222222222222"


@pytest.mark.asyncio
async def test_callback_happy_path_uses_first_org_as_default(client, mock_session):
    state = _make_state()
    orgs = [{"id": 100, "login": "acme"}, {"id": 200, "login": "widgets"}]
    fake_client = _github_http_client(orgs=orgs)

    user_result = MagicMock()
    user_result.scalar_one.return_value = "u-1"
    mock_session.execute = AsyncMock(return_value=user_result)

    with (
        patch("app.routers.auth._get_client", return_value=fake_client),
        patch("app.routers.auth._upsert_organization", AsyncMock(side_effect=["org-100", "org-200"])) as mock_org,
        patch("app.routers.auth._upsert_membership", AsyncMock(return_value="member")) as mock_membership,
    ):
        async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
            resp = await ac.get(
                f"/auth/github/callback?code=good-code&state={state}",
                cookies={"oauth_nonce": TEST_NONCE},
                follow_redirects=False,
            )

    assert resp.status_code == 302
    assert mock_org.await_count == 2
    mock_org.assert_any_await(mock_session, github_org_id=100, login="acme")
    mock_org.assert_any_await(mock_session, github_org_id=200, login="widgets")
    assert mock_membership.await_count == 2

    cookie_value = resp.headers["set-cookie"].split("session=", 1)[1].split(";", 1)[0]
    claims = jwt.decode(cookie_value, JWT_SECRET, algorithms=["HS256"])
    assert claims["org_id"] == "org-100"


@pytest.mark.asyncio
async def test_callback_orgs_fetch_failure_falls_back_to_personal_org(client, mock_session, caplog):
    """A rate-limited/failed /user/orgs must not be silently indistinguishable
    from "this account has no orgs" — it still degrades gracefully (personal
    org), but it must be logged so the discrepancy is traceable."""
    state = _make_state()
    fake_client = _github_http_client(orgs=[], orgs_status=403)

    user_result = MagicMock()
    user_result.scalar_one.return_value = "u-1"
    mock_session.execute = AsyncMock(return_value=user_result)

    with (
        patch("app.routers.auth._get_client", return_value=fake_client),
        patch("app.routers.auth._upsert_organization", AsyncMock(return_value="org-personal")) as mock_org,
        patch("app.routers.auth._upsert_membership", AsyncMock(return_value="owner")),
    ):
        async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
            with caplog.at_level("WARNING", logger="kubex.auth.github"):
                resp = await ac.get(
                    f"/auth/github/callback?code=good-code&state={state}",
                    cookies={"oauth_nonce": TEST_NONCE},
                    follow_redirects=False,
                )

    assert resp.status_code == 302
    mock_org.assert_awaited_once_with(mock_session, github_org_id=None, login="octocat")
    assert any("orgs fetch returned HTTP 403" in message for message in caplog.messages)


@pytest.mark.asyncio
async def test_callback_emails_fetch_failure_logs_and_continues(client, mock_session, caplog):
    """A failed /user/emails must not crash the login — it just means no
    primary email is known — but the failure should still be traceable."""
    state = _make_state()
    fake_client = _github_http_client(orgs=[], emails_status=403)

    user_result = MagicMock()
    user_result.scalar_one.return_value = "u-1"
    mock_session.execute = AsyncMock(return_value=user_result)

    with (
        patch("app.routers.auth._get_client", return_value=fake_client),
        patch("app.routers.auth._upsert_organization", AsyncMock(return_value="org-personal")),
        patch("app.routers.auth._upsert_membership", AsyncMock(return_value="owner")),
    ):
        async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
            with caplog.at_level("WARNING", logger="kubex.auth.github"):
                resp = await ac.get(
                    f"/auth/github/callback?code=good-code&state={state}",
                    cookies={"oauth_nonce": TEST_NONCE},
                    follow_redirects=False,
                )

    assert resp.status_code == 302
    assert any("email fetch returned HTTP 403" in message for message in caplog.messages)


# ── Real-Postgres tests for the upsert/role-assignment logic ────────────
# ON CONFLICT targets and "first member becomes owner" are exactly the
# kind of logic mocks can't catch bugs in — run these against a real
# instance (V012 schema applied), same testcontainers/DATABASE_URL
# pattern as test_dora_integration.py.

try:
    from testcontainers.postgres import PostgresContainer
    HAS_TESTCONTAINERS = True
except ImportError:
    HAS_TESTCONTAINERS = False

AUTH_TEST_DATABASE_URL = os.environ.get("AUTH_TEST_DATABASE_URL")

pytestmark_pg = pytest.mark.skipif(
    not (AUTH_TEST_DATABASE_URL or HAS_TESTCONTAINERS),
    reason="No database available (set AUTH_TEST_DATABASE_URL or install testcontainers)",
)


@pytest.fixture(scope="module")
def pg_url():
    container = None
    if AUTH_TEST_DATABASE_URL:
        url = AUTH_TEST_DATABASE_URL
    else:
        try:
            container = PostgresContainer("postgres:16-alpine")
            container.start()
            url = container.get_connection_url()
        except Exception:
            pytest.skip("Docker not available — skipping integration tests")

    import psycopg2

    conn = psycopg2.connect(url.replace("+psycopg2", ""))
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS schema_versions (
            version TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            description TEXT
        );
    """)
    migration_path = os.path.join(
        os.path.dirname(__file__), "..", "migrations", "V012__auth_tables.sql"
    )
    with open(migration_path) as f:
        cur.execute(f.read())
    cur.close()
    conn.close()

    yield url.replace("postgresql://", "postgresql+asyncpg://").replace("postgresql+psycopg2://", "postgresql+asyncpg://")

    if container:
        container.stop()


@pytest.fixture
async def pg_session(pg_url):
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    engine = create_async_engine(pg_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()
    async with engine.begin() as conn:
        from sqlalchemy import text
        await conn.execute(text("TRUNCATE org_memberships, api_keys, users, organizations RESTART IDENTITY CASCADE"))
    await engine.dispose()


@pytestmark_pg
class TestUpsertLogic:
    @pytest.mark.asyncio
    async def test_personal_org_created_with_login_as_slug(self, pg_session):
        org_id = await auth_router._upsert_organization(pg_session, github_org_id=None, login="octocat")
        await pg_session.commit()

        from sqlalchemy import select
        from app.models.organization import Organization

        row = (await pg_session.execute(select(Organization).where(Organization.id == org_id))).scalar_one()
        assert row.slug == "octocat"
        assert row.github_org_id is None

    @pytest.mark.asyncio
    async def test_personal_org_upsert_is_idempotent(self, pg_session):
        org_id_1 = await auth_router._upsert_organization(pg_session, github_org_id=None, login="octocat")
        org_id_2 = await auth_router._upsert_organization(pg_session, github_org_id=None, login="octocat")
        await pg_session.commit()
        assert org_id_1 == org_id_2

    @pytest.mark.asyncio
    async def test_github_org_upsert_keyed_on_github_org_id(self, pg_session):
        org_id_1 = await auth_router._upsert_organization(pg_session, github_org_id=555, login="acme")
        org_id_2 = await auth_router._upsert_organization(pg_session, github_org_id=555, login="acme-renamed")
        await pg_session.commit()

        assert org_id_1 == org_id_2
        from sqlalchemy import select
        from app.models.organization import Organization
        row = (await pg_session.execute(select(Organization).where(Organization.id == org_id_1))).scalar_one()
        assert row.name == "acme-renamed"
        # slug must be refreshed too, not just name — otherwise the old
        # handle stays claimed by this row and collides if a different
        # org later reuses it (slug is UNIQUE; the conflict target here
        # is github_org_id, so ON CONFLICT alone wouldn't catch that).
        assert row.slug == "acme-renamed"

    @pytest.mark.asyncio
    async def test_first_member_becomes_owner_second_becomes_member(self, pg_session):
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from app.models.user import User

        org_id = await auth_router._upsert_organization(pg_session, github_org_id=777, login="acme")

        user1 = (await pg_session.execute(
            pg_insert(User).values(github_id=1, login="alice").returning(User.id)
        )).scalar_one()
        user2 = (await pg_session.execute(
            pg_insert(User).values(github_id=2, login="bob").returning(User.id)
        )).scalar_one()

        role1 = await auth_router._upsert_membership(pg_session, user1, org_id)
        role2 = await auth_router._upsert_membership(pg_session, user2, org_id)
        await pg_session.commit()

        assert role1 == "owner"
        assert role2 == "member"

    @pytest.mark.asyncio
    async def test_relogin_returns_and_keeps_existing_role(self, pg_session):
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from sqlalchemy import select
        from app.models.user import User
        from app.models.org_membership import OrgMembership

        org_id = await auth_router._upsert_organization(pg_session, github_org_id=888, login="acme")
        user_id = (await pg_session.execute(
            pg_insert(User).values(github_id=3, login="carol").returning(User.id)
        )).scalar_one()

        first_role = await auth_router._upsert_membership(pg_session, user_id, org_id)
        assert first_role == "owner"

        # A second login must both report and persist the *actual* stored
        # role ('owner'), not whatever a fresh COUNT-based guess would say
        # for a "new" member ('member').
        second_role = await auth_router._upsert_membership(pg_session, user_id, org_id)
        await pg_session.commit()
        assert second_role == "owner"

        stored_role = (await pg_session.execute(
            select(OrgMembership.role).where(
                OrgMembership.user_id == user_id, OrgMembership.org_id == org_id
            )
        )).scalar_one()
        assert stored_role == "owner"
