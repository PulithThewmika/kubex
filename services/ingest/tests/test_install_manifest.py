"""Tests for the cluster-agent install-manifest endpoint (E22-T2, #657)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import bcrypt
import pytest
import yaml
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.models.cluster import Cluster


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
    assert "endpoints" in resources
    for rule in role["rules"]:
        if rule["resources"] == ["configmaps"]:
            assert set(rule["verbs"]) == {"get", "list", "watch", "patch"}
        else:
            assert set(rule["verbs"]) >= {"get", "list"}


@pytest.mark.asyncio
async def test_install_manifest_404_for_unknown_token(client: FastAPI, mock_session: AsyncMock) -> None:
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
    )

    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/install/kbx_nope.yaml")

    assert resp.status_code == 404
