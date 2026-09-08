"""JWT session middleware (E19-T3, EPIC-019).

Provides ``get_current_user`` and ``get_optional_user`` FastAPI
dependencies that validate the session cookie issued by the GitHub
OAuth callback and return a ``UserContext`` with the authenticated
user's IDs.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import JWT_SECRET
from .db import get_session
from .models.org_membership import OrgMembership


@dataclass(frozen=True, slots=True)
class UserContext:
    user_id: uuid.UUID
    org_id: uuid.UUID


def _decode_session(request: Request) -> UserContext | None:
    token = request.cookies.get("session")
    if not token:
        return None
    try:
        claims = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return UserContext(
            user_id=uuid.UUID(claims["user_id"]),
            org_id=uuid.UUID(claims["org_id"]),
        )
    except (jwt.PyJWTError, KeyError, TypeError, ValueError, AttributeError):
        return None


async def get_current_user(request: Request) -> UserContext:
    ctx = _decode_session(request)
    if ctx is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return ctx


async def get_optional_user(request: Request) -> UserContext | None:
    return _decode_session(request)


async def get_current_owner(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> UserContext:
    """Like ``get_current_user`` but 403s unless the caller is an *owner*
    of their active org. Guards mutations that grant KubeX access to a
    third-party account (E23-T5 — connecting/disconnecting Slack).

    Roles today are ``owner`` / ``member`` (see routers/auth.py); this is
    the first place the distinction is enforced.
    """
    ctx = await get_current_user(request)
    role = await session.scalar(
        select(OrgMembership.role).where(
            OrgMembership.user_id == ctx.user_id,
            OrgMembership.org_id == ctx.org_id,
        )
    )
    if role != "owner":
        raise HTTPException(status_code=403, detail="Organization owner role required")
    return ctx
