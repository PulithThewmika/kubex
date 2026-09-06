"""Remote cluster management (EPIC-022 / E22-T1).

Clusters authenticate with their own bcrypt-hashed bearer token
(app.auth.verify_cluster_token) rather than the user session JWT used
by the create/list endpoints below — see that function for the
rotation-grace-period lookup.
"""

from __future__ import annotations

import asyncio
import secrets

from fastapi import APIRouter, Depends
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

import bcrypt

from ..auth_middleware import UserContext, get_current_user
from ..db import get_session
from ..models.cluster import Cluster
from ..schemas.cluster import ClusterCreateRequest, ClusterCreateResponse

router = APIRouter(prefix="/api/clusters", tags=["clusters"])

TOKEN_PREFIX = "kbx_"


@router.post("", response_model=ClusterCreateResponse)
async def create_cluster(
    body: ClusterCreateRequest,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ClusterCreateResponse:
    token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    # bcrypt.hashpw is CPU-bound and has no async form — run it off the
    # event loop, matching verify_api_key/create_api_key's convention.
    token_hash = (await asyncio.to_thread(bcrypt.hashpw, token.encode(), bcrypt.gensalt())).decode()

    stmt = (
        pg_insert(Cluster)
        .values(org_id=user.org_id, name=body.name, token_hash=token_hash)
        .returning(Cluster.id, Cluster.name, Cluster.created_at)
    )
    row = (await session.execute(stmt)).one()
    await session.commit()

    return ClusterCreateResponse(id=str(row.id), name=row.name, token=token, created_at=row.created_at)
