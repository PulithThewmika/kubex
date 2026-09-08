from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ClusterCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=253)


class InstallInfoResponse(BaseModel):
    """Constants the Add Cluster wizard's Helm/GitOps command text needs —
    kept here (E22-T5, #806) so the frontend doesn't hand-duplicate values
    that already live in install.py's build_install_manifest(), which only
    the kubectl tab (GET /install/:token.yaml) previously read from."""

    ingest_public_url: str
    agent_namespace: str
    chart_repo_url: str
    chart_path: str


class ClusterCreateResponse(BaseModel):
    id: str
    name: str
    token: str
    created_at: datetime


class ClusterResponse(BaseModel):
    id: str
    name: str
    status: str
    agent_version: str | None
    argocd_version: str | None
    argocd_status: str | None
    prometheus_status: str | None
    prometheus_namespace: str | None = None
    prometheus_service: str | None = None
    last_heartbeat: datetime | None
    created_at: datetime


class ClusterVerifyResponse(BaseModel):
    id: str
    name: str
    org_id: str


class ClusterHeartbeatRequest(BaseModel):
    agent_version: str | None = None
    argocd_version: str | None = None
    argocd_status: str | None = None
    prometheus_status: str | None = None
    prometheus_namespace: str | None = None
    prometheus_service: str | None = None


class ClusterHeartbeatResponse(BaseModel):
    status: str
    last_heartbeat: datetime


class ClusterRotateTokenResponse(BaseModel):
    token: str
    grace_period_expires_at: datetime


class ClusterQueryResponse(BaseModel):
    id: str
    promql: str
    kind: str = "instant"
    params: dict | None = None


class ClusterQueryResultRequest(BaseModel):
    query_id: str
    result: dict
