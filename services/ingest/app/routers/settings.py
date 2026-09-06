"""Org settings — API key management (E19-T4, EPIC-019).

Keys are shown in full exactly once, at creation. Only a bcrypt hash is
stored; verification (app/auth.py:verify_api_key) walks every key's hash
since bcrypt hashes can't be looked up by index.
"""

from __future__ import annotations

import secrets

import bcrypt
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth_middleware import UserContext, get_current_user
from ..db import get_session
from ..models.api_key import ApiKey
from ..schemas.api_key import ApiKeyCreateRequest, ApiKeyCreateResponse

router = APIRouter(prefix="/api/settings/api-keys", tags=["settings"])

TOKEN_PREFIX = "dl_"


@router.post("", response_model=ApiKeyCreateResponse)
async def create_api_key(
    body: ApiKeyCreateRequest,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ApiKeyCreateResponse:
    token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    token_hash = bcrypt.hashpw(token.encode(), bcrypt.gensalt()).decode()

    key = ApiKey(org_id=user.org_id, name=body.name, token_hash=token_hash)
    session.add(key)
    await session.flush()
    await session.commit()

    return ApiKeyCreateResponse(
        id=str(key.id),
        name=key.name,
        token=token,
        created_at=key.created_at,
    )
