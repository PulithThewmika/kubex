"""Per-service integration tier: what's connected (CI, CD, Metrics) and what
features that unlocks (E23-T3, doc — connection status tracking).

Reuses the same columns/events the detection agent already resolves for
health scoring (E23-T2, agent/run.py) rather than re-deriving connectivity:
- CI: an active GitHub App installation whose repos[] contains service.repo.
- CD: cluster.argocd_status == 'found' takes priority; otherwise looked up
  from pipeline_events, which already logs every webhook delivery
  (CLAUDE.md "correlation decisions are logged at INFO").
- Metrics: cluster.prometheus_status == 'found', else health_check_url.
"""

from __future__ import annotations

import uuid
from typing import Literal, TypedDict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models.cluster import Cluster
from .models.installation import Installation
from .models.pipeline_event import PipelineEvent
from .models.service import Service

CDSource = Literal["argocd", "github_deployments", "webhook"]
MetricsSource = Literal["prometheus", "health_check"]


class IntegrationStatus(TypedDict):
    ci: bool
    cd: CDSource | None
    metrics: MetricsSource | None
    available_features: list[str]


async def _check_ci(session: AsyncSession, service: Service) -> bool:
    if not service.repo:
        return False
    result = await session.execute(
        select(Installation.id).where(
            Installation.org_id == service.org_id,
            Installation.status == "active",
            Installation.repos.any(service.repo),
        )
    )
    return result.first() is not None


async def _cluster_status(session: AsyncSession, cluster_id: uuid.UUID | None) -> tuple[str | None, str | None]:
    if cluster_id is None:
        return None, None
    result = await session.execute(
        select(Cluster.argocd_status, Cluster.prometheus_status).where(Cluster.id == cluster_id)
    )
    row = result.first()
    return (row.argocd_status, row.prometheus_status) if row else (None, None)


async def _check_cd(session: AsyncSession, service: Service, argocd_status: str | None) -> CDSource | None:
    if argocd_status == "found":
        return "argocd"

    if service.repo:
        result = await session.execute(
            select(PipelineEvent.id).where(
                PipelineEvent.org_id == service.org_id,
                PipelineEvent.source == "github_app",
                PipelineEvent.event_type == "deployment_status",
                PipelineEvent.payload["repository"]["full_name"].astext == service.repo,
            ).limit(1)
        )
        if result.first() is not None:
            return "github_deployments"

    result = await session.execute(
        select(PipelineEvent.id).where(
            PipelineEvent.org_id == service.org_id,
            PipelineEvent.source == "generic",
            PipelineEvent.event_type == "deploy_notify",
            PipelineEvent.payload["service"].astext == service.name,
        ).limit(1)
    )
    return "webhook" if result.first() is not None else None


def _check_metrics(service: Service, prometheus_status: str | None) -> MetricsSource | None:
    if prometheus_status == "found":
        return "prometheus"
    return "health_check" if service.health_check_url else None


def compute_available_features(ci: bool, cd: CDSource | None, metrics: MetricsSource | None) -> list[str]:
    features: list[str] = []
    if ci:
        features += ["deploy_tracking", "safety_scores", "dora_frequency", "dora_lead_time"]
    if cd is not None:
        features.append("dora_change_failure_rate")
    if metrics is not None:
        features += ["health_scoring", "dora_mttr"]
    if metrics == "prometheus":
        features.append("blast_radius")
    return features


async def get_service_integration_status(session: AsyncSession, service: Service) -> IntegrationStatus:
    argocd_status, prometheus_status = await _cluster_status(session, service.cluster_id)
    ci = await _check_ci(session, service)
    cd = await _check_cd(session, service, argocd_status)
    metrics = _check_metrics(service, prometheus_status)
    return IntegrationStatus(
        ci=ci, cd=cd, metrics=metrics,
        available_features=compute_available_features(ci, cd, metrics),
    )
