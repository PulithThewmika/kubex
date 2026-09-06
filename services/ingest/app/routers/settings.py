"""Org settings — API key management (E19-T4, EPIC-019).

Keys are shown in full exactly once, at creation. Only a bcrypt hash is
stored; verification (app/auth.py:verify_api_key) walks every key's hash
since bcrypt hashes can't be looked up by index.
"""

from __future__ import annotations

import secrets
import uuid

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth_middleware import UserContext, get_current_user
from ..db import get_session
from ..models.api_key import ApiKey
from ..schemas.api_key import ApiKeyCreateRequest, ApiKeyCreateResponse, ApiKeyResponse

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


@router.delete("/{key_id}", status_code=204)
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
