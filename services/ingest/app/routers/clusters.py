"""Remote cluster management (EPIC-022 / E22-T1).

Clusters authenticate with their own bcrypt-hashed bearer token
(app.auth.verify_cluster_token) rather than the user session JWT used
by the create/list endpoints below — see that function for the
rotation-grace-period lookup.
"""

from __future__ import annotations

import asyncio
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import bcrypt

from ..auth import verify_cluster_token
from ..auth_middleware import UserContext, get_current_user
from ..db import get_session
from ..models.cluster import Cluster
from ..models.cluster_query import ClusterQuery
from ..schemas.cluster import (
    ClusterCreateRequest,
    ClusterCreateResponse,
    ClusterHeartbeatRequest,
    ClusterHeartbeatResponse,
    ClusterQueryResponse,
    ClusterQueryResultRequest,
    ClusterResponse,
    ClusterRotateTokenResponse,
    ClusterVerifyResponse,
)

ROTATE_GRACE_PERIOD = timedelta(minutes=10)
# A relayed PromQL query older than this has no one waiting on it (see
# prom.py) — don't hand it to the agent to run.
STALE_QUERY_AGE = timedelta(seconds=60)


def _require_own_cluster(path_cluster_id: str, cluster: Cluster) -> None:
    """Cluster tokens authenticate a cluster, not a specific path id — reject
    a request whose token belongs to a different cluster than the one named
    in the URL rather than silently acting on the token's own cluster."""
    try:
        parsed = uuid.UUID(path_cluster_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid cluster id") from None
    if parsed != cluster.id:
        raise HTTPException(status_code=403, detail="Token does not match this cluster")

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
        prometheus_namespace=cluster.prometheus_namespace,
        prometheus_service=cluster.prometheus_service,
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
    try:
        row = (await session.execute(stmt)).one()
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        # 23505 = unique_violation. Only the (org_id, name) constraint can
        # fire here (org_id/token_hash are always present and org_id's FK
        # always resolves for an authenticated session) — but re-raise
        # anything else rather than mislabeling it as a name collision.
        if getattr(e.orig, "sqlstate", None) == "23505":
            raise HTTPException(status_code=409, detail="A cluster with this name already exists") from None
        raise

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


@router.post("/verify", response_model=ClusterVerifyResponse)
async def verify_cluster(cluster: Cluster = Depends(verify_cluster_token)) -> ClusterVerifyResponse:
    return ClusterVerifyResponse(id=str(cluster.id), name=cluster.name, org_id=str(cluster.org_id))


@router.post("/heartbeat", response_model=ClusterHeartbeatResponse)
async def cluster_heartbeat(
    body: ClusterHeartbeatRequest,
    cluster: Cluster = Depends(verify_cluster_token),
    session: AsyncSession = Depends(get_session),
) -> ClusterHeartbeatResponse:
    now = datetime.now(timezone.utc)
    values = {"last_heartbeat": now, "status": "connected"}
    if body.agent_version is not None:
        values["agent_version"] = body.agent_version
    if body.argocd_version is not None:
        values["argocd_version"] = body.argocd_version
    if body.argocd_status is not None:
        values["argocd_status"] = body.argocd_status
    if body.prometheus_status is not None:
        values["prometheus_status"] = body.prometheus_status
    if body.prometheus_namespace is not None:
        values["prometheus_namespace"] = body.prometheus_namespace
    if body.prometheus_service is not None:
        values["prometheus_service"] = body.prometheus_service

    # A Core UPDATE, not ORM attribute assignment: if a concurrent
    # disconnect-sweep (app.cluster_monitor) commits 'disconnected'
    # between this session's read of `cluster` (via verify_cluster_token)
    # and this commit, SQLAlchemy's dirty-tracking would see
    # `cluster.status = "connected"` as a no-op against the loaded value
    # and silently drop it from the UPDATE, leaving the row stuck
    # disconnected. Writing status unconditionally through Core sidesteps
    # that (caught by test_cluster_lifecycle_integration.py's
    # concurrent-lock tests).
    await session.execute(update(Cluster).where(Cluster.id == cluster.id).values(**values))
    await session.commit()

    return ClusterHeartbeatResponse(status="connected", last_heartbeat=now)


@router.get("/{cluster_id}/queries", response_model=list[ClusterQueryResponse])
async def list_pending_queries(
    cluster_id: str,
    cluster: Cluster = Depends(verify_cluster_token),
    session: AsyncSession = Depends(get_session),
) -> list[ClusterQueryResponse]:
    _require_own_cluster(cluster_id, cluster)

    # Skip rows nobody is waiting on any more: /api/prom deletes its row on
    # timeout, but an agent that was offline during the outage shouldn't
    # execute a backlog of stale queries against the customer's Prometheus
    # the moment it reconnects (prom.py's RELAY_TIMEOUT is 20s).
    cutoff = datetime.now(timezone.utc) - STALE_QUERY_AGE
    result = await session.execute(
        select(ClusterQuery)
        .where(
            ClusterQuery.cluster_id == cluster.id,
            ClusterQuery.status == "pending",
            ClusterQuery.requested_at >= cutoff,
        )
        .order_by(ClusterQuery.requested_at)
    )
    return [
        ClusterQueryResponse(id=str(q.id), promql=q.promql, kind=q.kind or "instant", params=q.params)
        for q in result.scalars().all()
    ]


@router.post("/{cluster_id}/results", status_code=204, response_model=None)
async def submit_query_result(
    cluster_id: str,
    body: ClusterQueryResultRequest,
    cluster: Cluster = Depends(verify_cluster_token),
    session: AsyncSession = Depends(get_session),
) -> None:
    _require_own_cluster(cluster_id, cluster)

    try:
        query_uuid = uuid.UUID(body.query_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid query id") from None

    stmt = (
        update(ClusterQuery)
        .where(ClusterQuery.id == query_uuid, ClusterQuery.cluster_id == cluster.id)
        .values(status="completed", result=body.result, completed_at=datetime.now(timezone.utc))
    )
    result = await session.execute(stmt)
    await session.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Query not found for this cluster")


@router.post("/{cluster_id}/rotate-token", response_model=ClusterRotateTokenResponse)
async def rotate_cluster_token(
    cluster_id: str,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ClusterRotateTokenResponse:
    try:
        cluster_uuid = uuid.UUID(cluster_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid cluster id") from None

    # SELECT ... FOR UPDATE: two concurrent rotations for the same cluster
    # must serialize, otherwise the second commit stores an
    # already-superseded token_hash into token_hash_old and the first
    # rotation's issued token never verifies (its grace record got
    # overwritten before it was ever read).
    result = await session.execute(
        select(Cluster).where(Cluster.id == cluster_uuid, Cluster.org_id == user.org_id).with_for_update()
    )
    cluster = result.scalar_one_or_none()
    if cluster is None:
        raise HTTPException(status_code=404, detail="Cluster not found")

    new_token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    new_token_hash = (await asyncio.to_thread(bcrypt.hashpw, new_token.encode(), bcrypt.gensalt())).decode()
    grace_expires_at = datetime.now(timezone.utc) + ROTATE_GRACE_PERIOD

    # Old token keeps verifying until grace_expires_at (verify_cluster_token
    # checks token_hash_old too) so an agent that hasn't picked up the new
    # token yet doesn't get locked out mid-rotation. token_hash and
    # token_hash_old/token_old_expires_at are set together in this one
    # UPDATE, so there's no window where a concurrent verify sees a new
    # token_hash with a stale/missing old-token grace record.
    cluster.token_hash_old = cluster.token_hash
    cluster.token_old_expires_at = grace_expires_at
    cluster.token_hash = new_token_hash
    await session.commit()

    return ClusterRotateTokenResponse(token=new_token, grace_period_expires_at=grace_expires_at)
