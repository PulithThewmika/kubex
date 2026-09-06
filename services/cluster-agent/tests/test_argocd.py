from __future__ import annotations

import base64
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from cluster_agent import argocd


def _secret(data: dict[str, str] | None) -> SimpleNamespace | None:
    if data is None:
        return None
    return SimpleNamespace(data={k: base64.b64encode(v.encode()).decode() for k, v in data.items()})


def _mock_secret_calls(existing_data: dict[str, str] | None) -> tuple[Any, Any]:
    """existing_data=None means the Secret already exists but has no
    relevant keys yet — pass a dict (possibly {}) for that. Use the
    sentinel MISSING to simulate the Secret object itself not existing."""
    return (
        patch("cluster_agent.k8s.get_secret", AsyncMock(return_value=_secret(existing_data))),
        patch("cluster_agent.k8s.patch_secret", AsyncMock()),
    )


@pytest.mark.asyncio
async def test_ensure_patched_skips_when_all_keys_already_match() -> None:
    desired = argocd.desired_notifications_data()
    desired_secret = argocd.desired_notifications_secret_data()
    cm = SimpleNamespace(data=dict(desired))

    get_secret_patch, patch_secret_patch = _mock_secret_calls(desired_secret)
    with (
        get_secret_patch,
        patch_secret_patch as mock_patch_secret,
        patch("cluster_agent.k8s.get_configmap", AsyncMock(return_value=cm)),
        patch("cluster_agent.k8s.patch_configmap", AsyncMock()) as mock_patch_cm,
        patch("cluster_agent.k8s.create_configmap", AsyncMock()) as mock_create_cm,
    ):
        patched = await argocd.ensure_patched("argocd")
    assert patched is False
    mock_patch_cm.assert_not_called()
    mock_create_cm.assert_not_called()
    mock_patch_secret.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_patched_writes_only_missing_or_stale_configmap_keys() -> None:
    desired = argocd.desired_notifications_data()
    desired_secret = argocd.desired_notifications_secret_data()
    some_key = next(iter(desired))
    existing = dict(desired)
    existing[some_key] = "stale-value"
    existing.pop(next(k for k in desired if k != some_key))  # drop one key entirely
    cm = SimpleNamespace(data=existing)

    get_secret_patch, patch_secret_patch = _mock_secret_calls(desired_secret)
    with (
        get_secret_patch,
        patch_secret_patch,
        patch("cluster_agent.k8s.get_configmap", AsyncMock(return_value=cm)),
        patch("cluster_agent.k8s.patch_configmap", AsyncMock()) as mock_patch_cm,
    ):
        patched = await argocd.ensure_patched("argocd")

    assert patched is True
    written = mock_patch_cm.call_args.args[2]
    assert some_key in written
    assert written[some_key] == desired[some_key]


@pytest.mark.asyncio
async def test_ensure_patched_creates_configmap_when_absent() -> None:
    desired_secret = argocd.desired_notifications_secret_data()
    get_secret_patch, patch_secret_patch = _mock_secret_calls(desired_secret)
    with (
        get_secret_patch,
        patch_secret_patch,
        patch("cluster_agent.k8s.get_configmap", AsyncMock(return_value=None)),
        patch("cluster_agent.k8s.patch_configmap", AsyncMock()) as mock_patch_cm,
        patch("cluster_agent.k8s.create_configmap", AsyncMock()) as mock_create_cm,
    ):
        patched = await argocd.ensure_patched("argocd")
    assert patched is True
    mock_create_cm.assert_awaited_once()
    mock_patch_cm.assert_not_called()  # PATCH 404s on a nonexistent object — must use create, not patch


@pytest.mark.asyncio
async def test_ensure_patched_raises_when_notifications_secret_is_absent() -> None:
    # Deliberately not auto-created: the Secret RBAC rule is resourceNames-
    # scoped, and "create" can't be scoped by resourceNames in K8s RBAC —
    # granting it would mean "create a Secret with any name" (see install.py).
    with (
        patch("cluster_agent.k8s.get_secret", AsyncMock(return_value=None)),
        patch("cluster_agent.k8s.get_configmap", AsyncMock(return_value=SimpleNamespace(data={}))),
    ):
        with pytest.raises(RuntimeError, match="argocd-notifications-secret"):
            await argocd.ensure_patched("argocd")


@pytest.mark.asyncio
async def test_ensure_patched_writes_secret_when_token_rotated() -> None:
    desired = argocd.desired_notifications_data()
    cm = SimpleNamespace(data=dict(desired))

    get_secret_patch, patch_secret_patch = _mock_secret_calls({"deploylens-agent-token": "stale-token"})
    with (
        get_secret_patch,
        patch_secret_patch as mock_patch_secret,
        patch("cluster_agent.k8s.get_configmap", AsyncMock(return_value=cm)),
        patch("cluster_agent.k8s.patch_configmap", AsyncMock()) as mock_patch_cm,
    ):
        patched = await argocd.ensure_patched("argocd")

    assert patched is True
    mock_patch_secret.assert_awaited_once()
    mock_patch_cm.assert_not_called()


def test_desired_notifications_data_references_secret_instead_of_embedding_token() -> None:
    webhook = argocd.desired_notifications_data()[f"service.webhook.{argocd._WEBHOOK_NAME}"]
    assert f"Bearer ${argocd._SECRET_KEY}\n" in webhook
    assert "kbx_" not in webhook  # a real cluster token is never embedded directly


def test_webhook_body_escapes_all_dynamic_fields_with_tojson() -> None:
    body = argocd._webhook_body("on-sync-failed")
    for field in (
        ".app.metadata.name",
        ".app.status.sync.status",
        ".app.status.sync.revision",
        ".app.status.health.status",
        ".app.status.operationState.phase",
        ".app.status.operationState.message",
        ".app.status.operationState.syncResult.revision",
        ".app.status.summary.images",
    ):
        assert f"{{{{toJson {field}}}}}" in body
    # bare interpolation (unescaped) would be a JSON-injection risk for
    # free-text fields like message/images — make sure none remains.
    assert '"{{.app' not in body


@pytest.mark.asyncio
async def test_discover_reports_rbac_denied() -> None:
    with patch("cluster_agent.k8s.find_argocd", AsyncMock(side_effect=argocd.k8s.RBACDeniedError("nope"))):
        result = await argocd.discover()
    assert result["status"] == "rbac_denied"


@pytest.mark.asyncio
async def test_discover_not_found_when_no_deployment_matches() -> None:
    with patch("cluster_agent.k8s.find_argocd", AsyncMock(return_value=None)):
        result = await argocd.discover()
    assert result == {"status": "not_found", "version": None, "namespace": None}


@pytest.mark.asyncio
async def test_discover_reports_error_on_non_rbac_k8s_failure() -> None:
    with patch("cluster_agent.k8s.find_argocd", AsyncMock(side_effect=RuntimeError("500 from apiserver"))):
        result = await argocd.discover()
    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_discover_reports_patch_failed_not_found_on_genuine_patch_error() -> None:
    with (
        patch("cluster_agent.k8s.find_argocd", AsyncMock(return_value=("argocd", "argocd-server"))),
        patch("cluster_agent.k8s.get_deployment", AsyncMock(return_value=None)),
        patch("cluster_agent.argocd.ensure_patched", AsyncMock(side_effect=RuntimeError("boom"))),
    ):
        result = await argocd.discover()
    assert result["status"] == "patch_failed"


class TestExtractVersion:
    def test_plain_tag(self) -> None:
        assert argocd._extract_version("quay.io/argoproj/argocd:v2.9.3") == "v2.9.3"

    def test_digest_pinned_with_no_tag_returns_none_not_the_digest(self) -> None:
        assert argocd._extract_version(
            "quay.io/argoproj/argocd@sha256:" + "a" * 64
        ) is None

    def test_registry_host_with_port_and_no_tag_returns_none(self) -> None:
        assert argocd._extract_version("registry.internal:5000/argoproj/argocd") is None

    def test_registry_host_with_port_and_tag(self) -> None:
        assert argocd._extract_version("registry.internal:5000/argoproj/argocd:v2.9.3") == "v2.9.3"

    def test_none_image(self) -> None:
        assert argocd._extract_version(None) is None
