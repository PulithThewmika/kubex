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
from fastapi import HTTPException, Request

from .auth import JWT_SECRET


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
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


async def get_current_user(request: Request) -> UserContext:
    ctx = _decode_session(request)
    if ctx is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return ctx


async def get_optional_user(request: Request) -> UserContext | None:
    return _decode_session(request)
