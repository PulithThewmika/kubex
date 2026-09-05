"""GitHub OAuth login (E19-T2, EPIC-019).

GET /auth/github redirects to GitHub's authorize page. GET
/auth/github/callback exchanges the returned code for an access token,
fetches the GitHub profile/orgs, upserts users/organizations/
org_memberships, and issues a session JWT as an httpOnly cookie.

The "state" param doubles as CSRF protection and redirect-target storage:
it's a short-lived JWT signed with JWT_SECRET, so the callback can verify
it wasn't forged without needing server-side session storage.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, JWT_SECRET
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
DEFAULT_REDIRECT = "/app"


def _safe_redirect_target(redirect: str | None) -> str:
    """Only allow same-site relative paths — anything else (an absolute
    URL, a protocol-relative "//evil.com") could turn the login flow into
    an open redirect."""
    if redirect and redirect.startswith("/") and not redirect.startswith("//"):
        return redirect
    return DEFAULT_REDIRECT


def _slugify(login: str) -> str:
    return login.lower()


@router.get("/github")
async def github_login(request: Request, redirect: str | None = Query(default=None)):
    target = _safe_redirect_target(redirect)
    state = jwt.encode(
        {
            "nonce": secrets.token_urlsafe(16),
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
    return RedirectResponse(url=f"{GITHUB_AUTHORIZE_URL}?{params}")


async def _upsert_github_org(session: AsyncSession, org: dict) -> int:
    """Upsert a real GitHub org, keyed on its stable github_org_id."""
    login = org["login"]
    stmt = pg_insert(Organization).values(
        github_org_id=org["id"],
        name=login,
        slug=_slugify(login),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["github_org_id"],
        index_where=Organization.github_org_id.is_not(None),
        set_={"name": stmt.excluded.name},
    )
    stmt = stmt.returning(Organization.id)
    return (await session.execute(stmt)).scalar_one()


async def _upsert_personal_org(session: AsyncSession, login: str) -> int:
    """Upsert the auto-created personal org for a user with no GitHub orgs.

    github_org_id is NULL for these (a plain UNIQUE constraint allows many
    NULLs, so it can't be the conflict target here) — slug, derived from
    the globally-unique GitHub login, is used instead.
    """
    stmt = pg_insert(Organization).values(
        github_org_id=None,
        name=login,
        slug=_slugify(login),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["slug"],
        set_={"name": stmt.excluded.name},
    )
    stmt = stmt.returning(Organization.id)
    return (await session.execute(stmt)).scalar_one()


async def _upsert_membership(session: AsyncSession, user_id, org_id) -> str:
    """Insert the membership if missing. The first member of an org becomes
    'owner', later joiners 'member' — and an existing membership's role is
    never changed by a later login."""
    existing_count = await session.scalar(
        select(func.count()).select_from(OrgMembership).where(OrgMembership.org_id == org_id)
    )
    role = "owner" if existing_count == 0 else "member"
    stmt = pg_insert(OrgMembership).values(user_id=user_id, org_id=org_id, role=role)
    stmt = stmt.on_conflict_do_nothing(index_elements=["user_id", "org_id"])
    await session.execute(stmt)
    return role


@router.get("/github/callback")
async def github_callback(
    request: Request,
    code: str,
    state: str,
    session: AsyncSession = Depends(get_session),
):
    try:
        claims = jwt.decode(state, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired OAuth state")
    redirect_target = claims.get("redirect", DEFAULT_REDIRECT)

    async with httpx.AsyncClient(timeout=10.0) as client:
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
        token_resp.raise_for_status()
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
        profile_resp.raise_for_status()
        profile = profile_resp.json()

        primary_email = None
        emails_resp = await client.get(f"{GITHUB_API_URL}/user/emails", headers=headers)
        if emails_resp.status_code == 200:
            for entry in emails_resp.json():
                if entry.get("primary"):
                    primary_email = entry.get("email")
                    break

        orgs_resp = await client.get(f"{GITHUB_API_URL}/user/orgs", headers=headers)
        orgs = orgs_resp.json() if orgs_resp.status_code == 200 else []

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

    default_org_id = None
    if orgs:
        for i, org in enumerate(orgs):
            org_id = await _upsert_github_org(session, org)
            await _upsert_membership(session, user_id, org_id)
            if i == 0:
                default_org_id = org_id
    else:
        default_org_id = await _upsert_personal_org(session, profile["login"])
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

    response = RedirectResponse(url=redirect_target, status_code=302)
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
