"""Tests for per-service integration status tracking (E23-T3)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.integration_status import (
    compute_available_features,
    get_service_integration_status,
)

ORG_ID = uuid4()


def _service(repo="org/orders", name="orders", cluster_id=None, health_check_url=None):
    return SimpleNamespace(
        org_id=ORG_ID, name=name, repo=repo,
        cluster_id=cluster_id, health_check_url=health_check_url,
    )


def _result(first=None):
    result = MagicMock()
    result.first.return_value = first
    return result


class TestComputeAvailableFeatures:
    def test_full_stack_gets_all_features(self):
        features = compute_available_features(True, "argocd", "prometheus")
        assert set(features) == {
            "deploy_tracking", "safety_scores", "dora_frequency", "dora_lead_time",
            "dora_change_failure_rate", "health_scoring", "dora_mttr", "blast_radius",
        }

    def test_ci_only_gets_ci_subset(self):
        features = compute_available_features(True, None, None)
        assert set(features) == {
            "deploy_tracking", "safety_scores", "dora_frequency", "dora_lead_time",
        }

    def test_no_connections_gets_nothing(self):
        assert compute_available_features(False, None, None) == []

    def test_health_check_metrics_excludes_blast_radius(self):
        features = compute_available_features(False, "webhook", "health_check")
        assert "blast_radius" not in features
        assert "health_scoring" in features


class TestGetServiceIntegrationStatus:
    @pytest.mark.asyncio
    async def test_no_cluster_no_installation_no_events(self):
        session = AsyncMock()
        # cluster_id is None -> _cluster_status short-circuits without a query.
        # order: _check_ci, _check_cd(github_deployments), _check_cd(webhook)
        session.execute = AsyncMock(side_effect=[_result(None), _result(None), _result(None)])

        status = await get_service_integration_status(session, _service(cluster_id=None))

        assert status["ci"] is False
        assert status["cd"] is None
        assert status["metrics"] is None
        assert status["available_features"] == []

    @pytest.mark.asyncio
    async def test_argocd_and_prometheus_and_ci(self):
        session = AsyncMock()
        cluster_row = MagicMock(argocd_status="found", prometheus_status="found")
        session.execute = AsyncMock(side_effect=[
            _result(cluster_row),   # _cluster_status
            _result(MagicMock()),  # _check_ci -> installation found
            # cd short-circuits to "argocd", no pipeline_events queries needed
        ])

        status = await get_service_integration_status(session, _service(cluster_id=uuid4()))

        assert status["ci"] is True
        assert status["cd"] == "argocd"
        assert status["metrics"] == "prometheus"
        assert "blast_radius" in status["available_features"]

    @pytest.mark.asyncio
    async def test_github_deployments_cd_fallback(self):
        session = AsyncMock()
        # cluster_id is None (no execute); repo is set so _check_ci and the
        # github_deployments lookup both query, but the second one hits
        # first and short-circuits before the webhook query ever runs.
        session.execute = AsyncMock(side_effect=[
            _result(None),         # _check_ci: no installation
            _result(MagicMock()),  # _check_cd: deployment_status event found
        ])

        status = await get_service_integration_status(session, _service())

        assert status["ci"] is False
        assert status["cd"] == "github_deployments"
        assert status["metrics"] is None

    @pytest.mark.asyncio
    async def test_webhook_cd_and_health_check_metrics(self):
        session = AsyncMock()
        # cluster_id is None (no execute for _cluster_status).
        session.execute = AsyncMock(side_effect=[
            _result(None),         # _check_ci
            _result(None),         # _check_cd: no deployment_status event
            _result(MagicMock()),  # _check_cd: generic notify event found
        ])

        status = await get_service_integration_status(
            session, _service(health_check_url="http://svc/healthz"),
        )

        assert status["cd"] == "webhook"
        assert status["metrics"] == "health_check"

    @pytest.mark.asyncio
    async def test_no_repo_skips_ci_and_github_deployments(self):
        session = AsyncMock()
        # No cluster (no execute), no repo -> _check_ci short-circuits (no
        # execute), _check_cd skips the github_deployments query (no repo)
        # and only queries the generic notify path.
        session.execute = AsyncMock(side_effect=[_result(None)])

        status = await get_service_integration_status(session, _service(repo=None))

        assert status["ci"] is False
        assert status["cd"] is None
        assert session.execute.await_count == 1
