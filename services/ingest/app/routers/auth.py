"""GitHub OAuth login (E19-T2, EPIC-019).

GET /auth/github redirects to GitHub's authorize page. GET
/auth/github/callback exchanges the returned code for an access token,
fetches the GitHub profile/orgs, upserts users/organizations/
org_memberships, and issues a session JWT as an httpOnly cookie.

The "state" param is a short-lived JWT signed with JWT_SECRET, so its
redirect-target and nonce claims can't be tampered with without a
server-side session store. The nonce alone doesn't stop a login-CSRF
attack though: without binding it to the specific browser that started
the flow, an attacker could complete their own login, capture the
resulting (validly-signed) state+code pair, and trick a victim into
visiting the callback with it — logging the victim into the attacker's
account. So the nonce is mirrored into a short-lived SameSite=Lax cookie
(Lax, not Strict, because it must still be sent back on the top-level GET
navigation GitHub redirects the browser through) and compared against
the state's copy in the callback.
"""

from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, JWT_SECRET, SHELL_URL
from ..db import get_session
from ..models.org_membership import OrgMembership
from ..models.organization import Organization
from ..models.user import User

logger = logging.getLogger("kubex.auth.github")

router = APIRouter(prefix="/auth", tags=["auth"])

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API_URL = "https://api.github.com"
OAUTH_SCOPES = "read:user user:email"

STATE_TTL_MINUTES = 10
SESSION_TTL_HOURS = 24
DEFAULT_REDIRECT_PATH = "/"
NONCE_COOKIE = "oauth_nonce"

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """Lazily-cached client, mirroring routers/grafana.py's pattern — a new
    AsyncClient per request would pay a fresh TCP/TLS handshake to GitHub
    on every single login instead of reusing a warm connection pool."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=10.0)
    return _client


def _safe_redirect_path(redirect: str | None) -> str:
    """Only allow same-site relative paths — anything else (an absolute
    URL, a protocol-relative "//evil.com", or a backslash variant like
    "/\\evil.com" that browsers' URL parser normalizes to "//evil.com")
    could turn the login flow into an open redirect."""
    if redirect and "\\" not in redirect:
        parsed = urlparse(redirect)
        if redirect.startswith("/") and not parsed.netloc and not parsed.scheme:
            return redirect
    return DEFAULT_REDIRECT_PATH


def _slugify(login: str) -> str:
    return login.lower()


@router.get("/github")
async def github_login(request: Request, redirect: str | None = Query(default=None)) -> RedirectResponse:
    target = _safe_redirect_path(redirect)
    nonce = secrets.token_urlsafe(16)
    state = jwt.encode(
        {
            "nonce": nonce,
            "redirect": target,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=STATE_TTL_MINUTES),
        },
        JWT_SECRET,
        algorithm="HS256",
    )
    params = httpx.QueryParams(
        {
            "client_id": GITHUB_CLIENT_ID,
            "redirect_uri": str(request.url_for("github_callback")),
            "scope": OAUTH_SCOPES,
            "state": state,
        }
    )
    # Cache-Control: no-store — a cached 302 here would replay a stale
    # state (and thus a stale redirect target/nonce) on the next visit,
    # bypassing the fresh state generated above.
    response = RedirectResponse(
        url=f"{GITHUB_AUTHORIZE_URL}?{params}",
        headers={"Cache-Control": "no-store"},
    )
    response.set_cookie(
        key=NONCE_COOKIE,
        value=nonce,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=STATE_TTL_MINUTES * 60,
        path="/auth/github",
    )
    return response


async def _upsert_organization(session: AsyncSession, *, github_org_id: int | None, login: str) -> uuid.UUID:
    """Upsert an organization row.

    Real GitHub orgs are keyed on the stable github_org_id. The
    auto-created personal org (github_org_id is NULL — a plain UNIQUE
    constraint allows many NULLs, so it can't be the conflict target
    there) is keyed on slug, derived from the globally-unique GitHub
    login, instead. Mirrors the correlation engine's commit_sha/image_tag
    dual-path upsert (CLAUDE.md architectural decision #1).
    """
    index_elements = ["github_org_id"] if github_org_id is not None else ["slug"]
    index_where = Organization.github_org_id.is_not(None) if github_org_id is not None else None
    stmt = pg_insert(Organization).values(
        github_org_id=github_org_id,
        name=login,
        slug=_slugify(login),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=index_elements,
        index_where=index_where,
        # slug is refreshed here too (not just name) so a renamed GitHub
        # org's row doesn't keep pointing at its old handle — a stale
        # slug could otherwise collide with a *different* org later
        # reusing that freed-up handle (slug is UNIQUE and this upsert's
        # conflict target is github_org_id, not slug, so that collision
        # wouldn't be caught by ON CONFLICT). For the personal-org path
        # (conflict target is already slug) this is a harmless no-op.
        set_={"name": stmt.excluded.name, "slug": stmt.excluded.slug},
    )
    stmt = stmt.returning(Organization.id)
    return (await session.execute(stmt)).scalar_one()


async def _upsert_membership(session: AsyncSession, user_id: uuid.UUID, org_id: uuid.UUID) -> str:
    """Insert the membership if missing and return the row's persisted
    role. The first member of an org becomes 'owner', later joiners
    'member' — and an existing membership's role is never changed by a
    later login.

    Locks the organization row first: without it, two different users
    completing their first login to the same brand-new org concurrently
    could both observe zero existing members and both become 'owner'
    (the ON CONFLICT target is (user_id, org_id), which only dedupes the
    same user re-inserting, not two different users racing the count).
    """
    await session.execute(select(Organization.id).where(Organization.id == org_id).with_for_update())
    existing_count = await session.scalar(
        select(func.count()).select_from(OrgMembership).where(OrgMembership.org_id == org_id)
    )
    role = "owner" if existing_count == 0 else "member"
    stmt = pg_insert(OrgMembership).values(user_id=user_id, org_id=org_id, role=role)
    stmt = stmt.on_conflict_do_update(
        index_elements=["user_id", "org_id"],
        # No-op self-assignment — purely so RETURNING gives back the
        # actually-persisted role on a conflict, instead of the role
        # freshly (and possibly wrongly) computed above for this call.
        set_={"role": OrgMembership.role},
    )
    stmt = stmt.returning(OrgMembership.role)
    return (await session.execute(stmt)).scalar_one()


@router.get("/github/callback")
async def github_callback(
    request: Request,
    code: str,
    state: str,
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    nonce_cookie = request.cookies.get(NONCE_COOKIE)
    try:
        claims = jwt.decode(state, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired OAuth state")
    if not nonce_cookie or not secrets.compare_digest(nonce_cookie, claims.get("nonce", "")):
        # Without this check, an attacker could complete their own OAuth
        # login, capture the resulting valid state+code, and trick a
        # victim's browser into visiting this callback — logging the
        # victim into the attacker's account (login CSRF). The signature
        # check above only proves the server issued this state to
        # *someone*; the nonce cookie proves it was issued to *this*
        # browser.
        raise HTTPException(status_code=401, detail="Missing or mismatched OAuth nonce")
    redirect_path = claims.get("redirect", DEFAULT_REDIRECT_PATH)

    client = _get_client()
    token_resp = await client.post(
        GITHUB_TOKEN_URL,
        data={
            "client_id": GITHUB_CLIENT_ID,
            "client_secret": GITHUB_CLIENT_SECRET,
            "code": code,
            "redirect_uri": str(request.url_for("github_callback")),
        },
        headers={"Accept": "application/json"},
    )
    try:
        token_resp.raise_for_status()
    except httpx.HTTPStatusError:
        logger.warning("GitHub token exchange returned HTTP %d", token_resp.status_code)
        raise HTTPException(status_code=502, detail="GitHub token exchange failed")
    token_data = token_resp.json()
    access_token = token_data.get("access_token")
    if not access_token:
        logger.warning(
            "GitHub token exchange failed: %s",
            token_data.get("error_description", token_data),
        )
        raise HTTPException(status_code=401, detail="GitHub token exchange failed")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
    }
    profile_resp = await client.get(f"{GITHUB_API_URL}/user", headers=headers)
    try:
        profile_resp.raise_for_status()
    except httpx.HTTPStatusError:
        logger.warning("GitHub profile fetch returned HTTP %d", profile_resp.status_code)
        raise HTTPException(status_code=502, detail="GitHub profile fetch failed")
    profile = profile_resp.json()

    primary_email = None
    emails_resp = await client.get(f"{GITHUB_API_URL}/user/emails", headers=headers)
    if emails_resp.status_code == 200:
        for entry in emails_resp.json():
            if entry.get("primary"):
                primary_email = entry.get("email")
                break
    else:
        logger.warning("GitHub email fetch returned HTTP %d for user %s", emails_resp.status_code, profile.get("login"))

    orgs_resp = await client.get(f"{GITHUB_API_URL}/user/orgs", headers=headers)
    if orgs_resp.status_code == 200:
        orgs = orgs_resp.json()
    else:
        # Not folded into the personal-org path silently — a rate-limited
        # or otherwise-failed /user/orgs call is not the same thing as
        # "this account really has no orgs", and treating it as such would
        # misroute an org member into a personal org with no indication
        # anything went wrong.
        logger.warning("GitHub orgs fetch returned HTTP %d for user %s", orgs_resp.status_code, profile.get("login"))
        orgs = []

    email = primary_email or profile.get("email")
    user_stmt = pg_insert(User).values(
        github_id=profile["id"],
        login=profile["login"],
        email=email,
        avatar_url=profile.get("avatar_url"),
    )
    user_stmt = user_stmt.on_conflict_do_update(
        index_elements=["github_id"],
        set_={
            "login": user_stmt.excluded.login,
            "email": user_stmt.excluded.email,
            "avatar_url": user_stmt.excluded.avatar_url,
        },
    )
    user_stmt = user_stmt.returning(User.id)
    user_id = (await session.execute(user_stmt)).scalar_one()

    default_org_id: uuid.UUID | None = None
    if orgs:
        for i, org in enumerate(orgs):
            org_id = await _upsert_organization(session, github_org_id=org["id"], login=org["login"])
            await _upsert_membership(session, user_id, org_id)
            if i == 0:
                default_org_id = org_id
    else:
        default_org_id = await _upsert_organization(session, github_org_id=None, login=profile["login"])
        await _upsert_membership(session, user_id, default_org_id)

    await session.commit()
    logger.info(
        "GitHub OAuth login: user_id=%s github_login=%s org_count=%d default_org_id=%s",
        user_id, profile["login"], len(orgs), default_org_id,
    )

    session_token = jwt.encode(
        {
            "user_id": str(user_id),
            "org_id": str(default_org_id),
            "exp": datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS),
        },
        JWT_SECRET,
        algorithm="HS256",
    )

    # redirect_path is always a validated same-site relative path (see
    # _safe_redirect_path) — it's resolved against the React shell's own
    # origin, not this API's, since that's where the post-login page
    # actually lives.
    redirect_url = urljoin(SHELL_URL, redirect_path)

    # Cache-Control: no-store — the callback URL embeds a one-time code
    # and this response sets the session cookie; a cached redirect here
    # could get replayed with a stale/consumed code on the next visit.
    response = RedirectResponse(
        url=redirect_url,
        status_code=302,
        headers={"Cache-Control": "no-store"},
    )
    response.delete_cookie(key=NONCE_COOKIE, path="/auth/github")
    response.set_cookie(
        key="session",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=SESSION_TTL_HOURS * 3600,
        path="/",
    )
    return response
