"""Per-service integration tier: what's connected (CI, CD, Metrics) and what
features that unlocks (E23-T3, doc — connection status tracking).

Reuses the same columns/events the detection agent already resolves for
health scoring (E23-T2, agent/run.py) rather than re-deriving connectivity:
- CI: an active GitHub App installation whose repos[] contains service.repo,
  OR a pipeline_events row from the legacy per-repo webhook (source=
  'github_actions', event_type='workflow_run' — CLAUDE.md decision 10, this
  path still serves the sample app).
- CD: cluster.argocd_status == 'found', OR a pipeline_events row from the
  ArgoCD Notifications webhook (source='argocd', matched on
  service.argocd_app — webhooks_argocd.py) takes priority as 'argocd';
  otherwise falls back to 'github_deployments' (github_app deployment_status
  events) or 'webhook' (the generic /api/deployments/notify endpoint).
  pipeline_events already logs every webhook delivery (CLAUDE.md
  "correlation decisions are logged at INFO").
- Metrics: cluster.prometheus_status == 'found', else health_check_url.

Status is resolved for a whole org's services in one batch
(load_integration_context) rather than per-service, so GET /api/services
stays a handful of queries regardless of service count (CodeRabbit, PR #809)
instead of an N+1 fan-out.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Literal, Protocol, TypedDict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models.cluster import Cluster
from .models.installation import Installation
from .models.pipeline_event import PipelineEvent

CDSource = Literal["argocd", "github_deployments", "webhook"]
MetricsSource = Literal["prometheus", "health_check"]


class IntegrationStatus(TypedDict):
    ci: bool
    cd: CDSource | None
    metrics: MetricsSource | None
    available_features: list[str]


class ServiceLike(Protocol):
    org_id: uuid.UUID
    name: str
    repo: str | None
    argocd_app: str | None
    cluster_id: uuid.UUID | None
    health_check_url: str | None


@dataclass
class IntegrationContext:
    ci_repos: set[str] = field(default_factory=set)
    cluster_statuses: dict[uuid.UUID, tuple[str | None, str | None]] = field(default_factory=dict)
    argocd_apps: set[str] = field(default_factory=set)
    github_deployment_repos: set[str] = field(default_factory=set)
    webhook_notify_services: set[str] = field(default_factory=set)


async def _load_ci_repos(session: AsyncSession, org_id: uuid.UUID) -> set[str]:
    installations_result = await session.execute(
        select(Installation.repos).where(Installation.org_id == org_id, Installation.status == "active")
    )
    repos: set[str] = set()
    for (repo_list,) in installations_result.all():
        repos.update(repo_list or [])

    # Legacy per-repo webhook (CLAUDE.md decision 10) — still serves the
    # sample app, which has no GitHub App installation.
    legacy_result = await session.execute(
        select(PipelineEvent.payload["repository"]["full_name"].astext)
        .where(
            PipelineEvent.org_id == org_id,
            PipelineEvent.source == "github_actions",
            PipelineEvent.event_type == "workflow_run",
        )
        .distinct()
    )
    repos.update(repo for (repo,) in legacy_result.all() if repo)
    return repos


async def _load_argocd_apps(session: AsyncSession, org_id: uuid.UUID) -> set[str]:
    result = await session.execute(
        select(PipelineEvent.payload["app"]["metadata"]["name"].astext)
        .where(PipelineEvent.org_id == org_id, PipelineEvent.source == "argocd")
        .distinct()
    )
    return {app for (app,) in result.all() if app}


async def _load_cluster_statuses(session: AsyncSession, org_id: uuid.UUID) -> dict[uuid.UUID, tuple[str | None, str | None]]:
    result = await session.execute(
        select(Cluster.id, Cluster.argocd_status, Cluster.prometheus_status).where(Cluster.org_id == org_id)
    )
    return {row.id: (row.argocd_status, row.prometheus_status) for row in result.all()}


async def _load_github_deployment_repos(session: AsyncSession, org_id: uuid.UUID) -> set[str]:
    result = await session.execute(
        select(PipelineEvent.payload["repository"]["full_name"].astext)
        .where(
            PipelineEvent.org_id == org_id,
            PipelineEvent.source == "github_app",
            PipelineEvent.event_type == "deployment_status",
        )
        .distinct()
    )
    return {repo for (repo,) in result.all() if repo}


async def _load_webhook_notify_services(session: AsyncSession, org_id: uuid.UUID) -> set[str]:
    result = await session.execute(
        select(PipelineEvent.payload["service"].astext)
        .where(
            PipelineEvent.org_id == org_id,
            PipelineEvent.source == "generic",
            PipelineEvent.event_type == "deploy_notify",
        )
        .distinct()
    )
    return {name for (name,) in result.all() if name}


async def load_integration_context(session: AsyncSession, org_id: uuid.UUID) -> IntegrationContext:
    """One batch of org-wide queries backing every service's integration
    status — call once per request, not once per service.

    Run serially, not via asyncio.gather: a single AsyncSession isn't safe
    to use concurrently across tasks (SQLAlchemy 2.x asyncio docs).
    """
    ci_repos = await _load_ci_repos(session, org_id)
    cluster_statuses = await _load_cluster_statuses(session, org_id)
    argocd_apps = await _load_argocd_apps(session, org_id)
    github_deployment_repos = await _load_github_deployment_repos(session, org_id)
    webhook_notify_services = await _load_webhook_notify_services(session, org_id)
    return IntegrationContext(
        ci_repos=ci_repos,
        cluster_statuses=cluster_statuses,
        argocd_apps=argocd_apps,
        github_deployment_repos=github_deployment_repos,
        webhook_notify_services=webhook_notify_services,
    )


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


def get_service_integration_status(context: IntegrationContext, service: ServiceLike) -> IntegrationStatus:
    ci = bool(service.repo) and service.repo in context.ci_repos

    argocd_status, prometheus_status = context.cluster_statuses.get(service.cluster_id, (None, None))
    cd: CDSource | None
    if argocd_status == "found" or (service.argocd_app and service.argocd_app in context.argocd_apps):
        cd = "argocd"
    elif service.repo and service.repo in context.github_deployment_repos:
        cd = "github_deployments"
    elif service.name in context.webhook_notify_services:
        cd = "webhook"
    else:
        cd = None

    metrics: MetricsSource | None
    if prometheus_status == "found":
        metrics = "prometheus"
    elif service.health_check_url:
        metrics = "health_check"
    else:
        metrics = None

    return IntegrationStatus(
        ci=ci, cd=cd, metrics=metrics,
        available_features=compute_available_features(ci, cd, metrics),
    )
