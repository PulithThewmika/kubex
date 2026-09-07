"""Tests for the cluster-agent install-manifest endpoint (E22-T2, #657)."""

from __future__ import annotations

import shutil
import subprocess
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import bcrypt
import pytest
import yaml
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.models.cluster import Cluster
from app.routers.install import build_install_manifest

_CHART_DIR = Path(__file__).resolve().parents[3] / "deploy" / "helm" / "cluster-agent"


def _rules_by_resources(rules: list[dict]) -> dict[tuple[str, ...], dict]:
    return {
        tuple(sorted(rule["resources"])): {
            "verbs": set(rule["verbs"]),
            "resourceNames": set(rule.get("resourceNames", [])),
        }
        for rule in rules
    }


@pytest.mark.skipif(shutil.which("helm") is None, reason="helm CLI not installed")
def test_helm_chart_clusterrole_matches_install_manifest() -> None:
    """E22-T4 (#802 review): the Helm chart's clusterrole.yaml is a
    hand-copy of build_install_manifest()'s RBAC rules, kept in sync only
    by a comment. Render the real chart and diff its rules against this
    function's own output so a future edit to one that forgets the other
    fails CI instead of silently diverging."""
    raw_manifest = build_install_manifest("test-token", "https://ingest.example.com")
    raw_role = next(doc for doc in yaml.safe_load_all(raw_manifest) if doc["kind"] == "ClusterRole")

    rendered = subprocess.run(
        [
            "helm",
            "template",
            "test",
            str(_CHART_DIR),
            "--set",
            "token=x",
            "--set",
            "endpoint=https://e",
            "--set",
            "image.tag=abc1234",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    chart_role = next(doc for doc in yaml.safe_load_all(rendered.stdout) if doc["kind"] == "ClusterRole")

    assert _rules_by_resources(chart_role["rules"]) == _rules_by_resources(raw_role["rules"])


def _fake_cluster(token: str) -> Cluster:
    return Cluster(
        id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        name="prod-cluster",
        token_hash=bcrypt.hashpw(token.encode(), bcrypt.gensalt()).decode(),
        token_hash_old=None,
        token_old_expires_at=None,
        agent_version=None,
        argocd_version=None,
        argocd_status=None,
        prometheus_status=None,
        last_heartbeat=None,
        status="pending",
        created_at=datetime.now(timezone.utc),
    )


# ── #661: valid token returns parseable Kubernetes YAML ─────────────────


@pytest.mark.asyncio
@patch("app.routers.install.INGEST_PUBLIC_URL", "https://ingest.example.com")
async def test_install_manifest_returns_valid_kubernetes_yaml(client: FastAPI, mock_session: AsyncMock) -> None:
    token = "kbx_" + "a" * 40
    cluster = _fake_cluster(token)
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[cluster]))))
    )

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get(f"/install/{token}.yaml")

    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "no-store"

    docs = list(yaml.safe_load_all(resp.text))
    by_kind = {d["kind"]: d for d in docs}
    assert set(by_kind) == {
        "Namespace",
        "ServiceAccount",
        "ClusterRole",
        "ClusterRoleBinding",
        "Secret",
        "Deployment",
    }

    for doc in docs:
        assert "apiVersion" in doc
        assert "metadata" in doc and "name" in doc["metadata"]

    secret = by_kind["Secret"]
    assert secret["stringData"]["CLUSTER_TOKEN"] == token

    deployment = by_kind["Deployment"]
    containers = deployment["spec"]["template"]["spec"]["containers"]
    assert containers[0]["image"].startswith("ghcr.io/")
    env_names = {e["name"] for e in containers[0]["env"]}
    assert "DEPLOYLENS_ENDPOINT" in env_names
    assert "CLUSTER_TOKEN" in env_names

    role = by_kind["ClusterRole"]
    resources = {r for rule in role["rules"] for r in rule["resources"]}
    assert "configmaps" in resources
    assert "services" in resources
    assert "deployments" in resources
    assert "secrets" in resources
    for rule in role["rules"]:
        if rule["resources"] == ["configmaps"]:
            assert set(rule["verbs"]) == {"get", "list", "create", "patch"}
        elif rule["resources"] == ["secrets"]:
            # Scoped to exactly one Secret name, not a blanket cluster-wide
            # grant — this is what lets the agent patch its own bearer
            # token into argocd-notifications-secret without being able to
            # read any other Secret in the cluster.
            assert rule["resourceNames"] == ["argocd-notifications-secret"]
            assert set(rule["verbs"]) == {"get", "patch"}
        else:
            assert set(rule["verbs"]) >= {"get", "list"}


@pytest.mark.asyncio
@patch("app.routers.install.INGEST_PUBLIC_URL", "https://ingest.example.com")
async def test_install_manifest_404_for_unknown_token(client: FastAPI, mock_session: AsyncMock) -> None:
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
    )

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/install/kbx_nope.yaml")

    assert resp.status_code == 404
    assert resp.headers["cache-control"] == "no-store"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "loopback_url",
    [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://127.0.0.2:8000",  # whole 127.0.0.0/8 is loopback, not just .1
        "http://[::1]:8000",
        "http://[0:0:0:0:0:0:0:1]:8000",  # expanded IPv6 loopback form
    ],
)
async def test_install_manifest_500_when_ingest_public_url_is_loopback(
    client: FastAPI, mock_session: AsyncMock, loopback_url: str
) -> None:
    """A manifest embedding a loopback DEPLOYLENS_ENDPOINT would deploy an
    agent that can never reach this service — reject before even looking up
    the token, per CodeRabbit's PR #800 finding. Covers the whole loopback
    range/expanded IPv6 forms, not just the exact default value."""
    with patch("app.routers.install.INGEST_PUBLIC_URL", loopback_url):
        async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
            resp = await ac.get("/install/kbx_anything.yaml")

    assert resp.status_code == 500
    assert resp.headers["cache-control"] == "no-store"
    mock_session.execute.assert_not_awaited()


@pytest.mark.asyncio
@patch("app.routers.install.INGEST_PUBLIC_URL", "https://ingest.example.com")
async def test_install_manifest_404_for_grace_period_old_token(client: FastAPI, mock_session: AsyncMock) -> None:
    """A token that only matches token_hash_old (post-rotation grace window,
    E22-T1-S10) must be rejected here — baking it into a generated manifest
    would deploy an agent whose credential silently expires within the
    10-minute grace period, with nothing in the YAML to indicate that."""
    old_token = "kbx_" + "old" * 15
    new_token = "kbx_" + "new" * 15
    cluster = _fake_cluster(new_token)
    cluster.token_hash_old = bcrypt.hashpw(old_token.encode(), bcrypt.gensalt()).decode()
    cluster.token_old_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[cluster]))))
    )

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get(f"/install/{old_token}.yaml")

    assert resp.status_code == 404
