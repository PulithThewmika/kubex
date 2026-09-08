"""Tests for per-service integration status tracking (E23-T3)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from app.integration_status import (
    IntegrationContext,
    compute_available_features,
    get_service_integration_status,
    load_integration_context,
)

ORG_ID = uuid4()


def _service(
    repo: str | None = "org/orders",
    name: str = "orders",
    argocd_app: str | None = None,
    cluster_id: UUID | None = None,
    health_check_url: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        org_id=ORG_ID, name=name, repo=repo, argocd_app=argocd_app,
        cluster_id=cluster_id, health_check_url=health_check_url,
    )


class TestComputeAvailableFeatures:
    def test_full_stack_gets_all_features(self) -> None:
        features = compute_available_features(True, "argocd", "prometheus")
        assert set(features) == {
            "deploy_tracking", "safety_scores", "dora_frequency", "dora_lead_time",
            "dora_change_failure_rate", "health_scoring", "dora_mttr", "blast_radius",
        }

    def test_ci_only_gets_ci_subset(self) -> None:
        features = compute_available_features(True, None, None)
        assert set(features) == {
            "deploy_tracking", "safety_scores", "dora_frequency", "dora_lead_time",
        }

    def test_no_connections_gets_nothing(self) -> None:
        assert compute_available_features(False, None, None) == []

    def test_health_check_metrics_excludes_blast_radius(self) -> None:
        features = compute_available_features(False, "webhook", "health_check")
        assert "blast_radius" not in features
        assert "health_scoring" in features


class TestGetServiceIntegrationStatus:
    def test_no_cluster_no_installation_no_events(self) -> None:
        context = IntegrationContext()

        status = get_service_integration_status(context, _service())

        assert status["ci"] is False
        assert status["cd"] is None
        assert status["metrics"] is None
        assert status["available_features"] == []

    def test_argocd_and_prometheus_and_ci(self) -> None:
        cluster_id = uuid4()
        context = IntegrationContext(
            ci_repos={"org/orders"},
            cluster_statuses={cluster_id: ("found", "found")},
        )

        status = get_service_integration_status(context, _service(cluster_id=cluster_id))

        assert status["ci"] is True
        assert status["cd"] == "argocd"
        assert status["metrics"] == "prometheus"
        assert "blast_radius" in status["available_features"]

    def test_legacy_argocd_notifications_webhook_counts_as_argocd(self) -> None:
        """No cluster-agent (argocd_status), but the legacy ArgoCD
        Notifications webhook has logged events for this app."""
        context = IntegrationContext(argocd_apps={"orders-app"})

        status = get_service_integration_status(context, _service(argocd_app="orders-app"))

        assert status["cd"] == "argocd"

    def test_legacy_github_actions_webhook_counts_as_ci(self) -> None:
        """No GitHub App installation, but the legacy per-repo webhook
        (CLAUDE.md decision 10 — still serves the sample app) has events."""
        context = IntegrationContext(ci_repos={"org/orders"})

        status = get_service_integration_status(context, _service(repo="org/orders"))

        assert status["ci"] is True

    def test_github_deployments_cd_fallback(self) -> None:
        context = IntegrationContext(github_deployment_repos={"org/orders"})

        status = get_service_integration_status(context, _service())

        assert status["ci"] is False
        assert status["cd"] == "github_deployments"
        assert status["metrics"] is None

    def test_webhook_cd_and_health_check_metrics(self) -> None:
        context = IntegrationContext(webhook_notify_services={"orders"})

        status = get_service_integration_status(
            context, _service(health_check_url="http://svc/healthz"),
        )

        assert status["cd"] == "webhook"
        assert status["metrics"] == "health_check"

    def test_no_repo_skips_ci_and_github_deployments(self) -> None:
        context = IntegrationContext(
            github_deployment_repos={"org/other"}, webhook_notify_services={"other-service"},
        )

        status = get_service_integration_status(context, _service(repo=None, name="orders"))

        assert status["ci"] is False
        assert status["cd"] is None

    def test_unknown_cluster_id_defaults_to_no_status(self) -> None:
        context = IntegrationContext(cluster_statuses={uuid4(): ("found", "found")})

        status = get_service_integration_status(context, _service(cluster_id=uuid4()))

        assert status["cd"] is None
        assert status["metrics"] is None


class TestLoadIntegrationContext:
    @pytest.mark.asyncio
    async def test_combines_all_five_prefetch_queries(self) -> None:
        cluster_id = uuid4()
        session = AsyncMock()
        with (
            patch("app.integration_status._load_ci_repos", AsyncMock(return_value={"org/a"})),
            patch(
                "app.integration_status._load_cluster_statuses",
                AsyncMock(return_value={cluster_id: ("found", "found")}),
            ),
            patch("app.integration_status._load_argocd_apps", AsyncMock(return_value={"orders-app"})),
            patch(
                "app.integration_status._load_github_deployment_repos", AsyncMock(return_value={"org/b"}),
            ),
            patch(
                "app.integration_status._load_webhook_notify_services", AsyncMock(return_value={"service-c"}),
            ),
        ):
            context = await load_integration_context(session, ORG_ID)

        assert context.ci_repos == {"org/a"}
        assert context.cluster_statuses == {cluster_id: ("found", "found")}
        assert context.argocd_apps == {"orders-app"}
        assert context.github_deployment_repos == {"org/b"}
        assert context.webhook_notify_services == {"service-c"}
