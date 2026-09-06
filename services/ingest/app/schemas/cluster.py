from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ClusterCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=253)


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


class ClusterHeartbeatResponse(BaseModel):
    status: str
    last_heartbeat: datetime


class ClusterRotateTokenResponse(BaseModel):
    token: str
    grace_period_expires_at: datetime


class ClusterQueryResponse(BaseModel):
    id: str
    promql: str


class ClusterQueryResultRequest(BaseModel):
    query_id: str
    result: dict
