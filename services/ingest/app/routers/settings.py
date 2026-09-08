"""Org settings — API key management (E19-T4, EPIC-019).

Keys are shown in full exactly once, at creation. Only a bcrypt hash is
stored; verification (app/auth.py:verify_api_key) walks every key's hash
since bcrypt hashes can't be looked up by index.
"""

from __future__ import annotations

import asyncio
import secrets
import uuid

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth_middleware import UserContext, get_current_user
from ..db import get_session
from ..models.api_key import ApiKey
from ..models.installation import Installation
from ..models.org_membership import OrgMembership
from ..models.organization import Organization
from ..models.user import User
from ..schemas.api_key import ApiKeyCreateRequest, ApiKeyCreateResponse, ApiKeyResponse
from ..schemas.installation import InstallationResponse
from ..schemas.member import MemberResponse

router = APIRouter(prefix="/api/settings/api-keys", tags=["settings"])
installations_router = APIRouter(prefix="/api/settings/installations", tags=["settings"])
onboarding_router = APIRouter(prefix="/api/settings/onboarding", tags=["settings"])
members_router = APIRouter(prefix="/api/settings/members", tags=["settings"])

TOKEN_PREFIX = "dl_"


@router.post("", response_model=ApiKeyCreateResponse)
async def create_api_key(
    body: ApiKeyCreateRequest,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ApiKeyCreateResponse:
    token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    # bcrypt.hashpw is CPU-bound and has no async form — run it off the
    # event loop so one key creation doesn't stall every other in-flight
    # request on this worker.
    token_hash = (await asyncio.to_thread(bcrypt.hashpw, token.encode(), bcrypt.gensalt())).decode()

    stmt = (
        pg_insert(ApiKey)
        .values(org_id=user.org_id, name=body.name, token_hash=token_hash)
        .returning(ApiKey.id, ApiKey.name, ApiKey.created_at)
    )
    row = (await session.execute(stmt)).one()
    await session.commit()

    return ApiKeyCreateResponse(
        id=str(row.id),
        name=row.name,
        token=token,
        created_at=row.created_at,
    )


@router.get("", response_model=list[ApiKeyResponse])
async def list_api_keys(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ApiKeyResponse]:
    result = await session.execute(
        select(ApiKey).where(ApiKey.org_id == user.org_id).order_by(ApiKey.created_at.desc())
    )
    return [
        ApiKeyResponse(id=str(k.id), name=k.name, created_at=k.created_at, last_used=k.last_used)
        for k in result.scalars().all()
    ]


@router.delete("/{key_id}", status_code=204, response_model=None)
async def revoke_api_key(
    key_id: str,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    try:
        key_uuid = uuid.UUID(key_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid key id") from None

    result = await session.execute(
        delete(ApiKey).where(ApiKey.id == key_uuid, ApiKey.org_id == user.org_id)
    )
    await session.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="API key not found")


@installations_router.get("", response_model=list[InstallationResponse])
async def list_installations(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[InstallationResponse]:
    result = await session.execute(
        select(Installation)
        .where(Installation.org_id == user.org_id)
        .order_by(Installation.created_at.desc())
    )
    return [
        InstallationResponse(
            id=str(i.id),
            github_installation_id=i.github_installation_id,
            account_login=i.account_login,
            repos=i.repos,
            status=i.status,
            created_at=i.created_at,
        )
        for i in result.scalars().all()
    ]


@members_router.get("", response_model=list[MemberResponse])
async def list_members(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[MemberResponse]:
    """Members of the caller's active org (Team tab, E24-T3-S5). Org-scoped
    per CLAUDE.md decision 9 — only rows for `user.org_id` are returned."""
    result = await session.execute(
        select(User.id, User.login, User.avatar_url, OrgMembership.role, OrgMembership.joined_at)
        .join(OrgMembership, OrgMembership.user_id == User.id)
        .where(OrgMembership.org_id == user.org_id)
        .order_by(OrgMembership.joined_at)
    )
    return [
        MemberResponse(
            user_id=str(row.id),
            login=row.login,
            avatar_url=row.avatar_url,
            role=row.role,
            joined_at=row.joined_at,
        )
        for row in result.all()
    ]


@onboarding_router.post("/complete", status_code=204, response_model=None)
async def complete_onboarding(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Mark the caller's org as having finished (or skipped) the onboarding
    wizard (E24-T2-S6). Idempotent — re-running it is a no-op. The wizard
    stays reachable from Settings regardless of this flag; it only controls
    the first-login auto-redirect."""
    result = await session.execute(
        update(Organization).where(Organization.id == user.org_id).values(onboarding_completed=True)
    )
    await session.commit()
    # A valid JWT outlives its org (deletion cascades memberships, not
    # tokens) — 0 rows means the org is gone, so don't report success.
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Organization not found")
