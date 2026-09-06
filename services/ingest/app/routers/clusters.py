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
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

import bcrypt

from ..auth_middleware import UserContext, get_current_user
from ..db import get_session
from ..models.cluster import Cluster
from ..schemas.cluster import ClusterCreateRequest, ClusterCreateResponse, ClusterResponse

router = APIRouter(prefix="/api/clusters", tags=["clusters"])

TOKEN_PREFIX = "kbx_"


def _to_response(cluster: Cluster) -> ClusterResponse:
    return ClusterResponse(
        id=str(cluster.id),
        name=cluster.name,
        status=cluster.status,
        agent_version=cluster.agent_version,
        argocd_version=cluster.argocd_version,
        argocd_status=cluster.argocd_status,
        prometheus_status=cluster.prometheus_status,
        last_heartbeat=cluster.last_heartbeat,
        created_at=cluster.created_at,
    )


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


@router.get("", response_model=list[ClusterResponse])
async def list_clusters(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ClusterResponse]:
    result = await session.execute(
        select(Cluster).where(Cluster.org_id == user.org_id).order_by(Cluster.created_at.desc())
    )
    return [_to_response(c) for c in result.scalars().all()]
