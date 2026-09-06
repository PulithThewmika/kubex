from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from cluster_agent import argocd


@pytest.mark.asyncio
async def test_ensure_patched_skips_when_all_keys_already_match():
    desired = argocd.desired_notifications_data()
    cm = SimpleNamespace(data=dict(desired))
    with (
        patch("cluster_agent.k8s.get_configmap", AsyncMock(return_value=cm)),
        patch("cluster_agent.k8s.patch_configmap", AsyncMock()) as mock_patch,
    ):
        patched = await argocd.ensure_patched("argocd")
    assert patched is False
    mock_patch.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_patched_writes_only_missing_or_stale_keys():
    desired = argocd.desired_notifications_data()
    some_key = next(iter(desired))
    existing = dict(desired)
    existing[some_key] = "stale-value"
    existing.pop(next(k for k in desired if k != some_key))  # drop one key entirely
    cm = SimpleNamespace(data=existing)

    with (
        patch("cluster_agent.k8s.get_configmap", AsyncMock(return_value=cm)),
        patch("cluster_agent.k8s.patch_configmap", AsyncMock()) as mock_patch,
    ):
        patched = await argocd.ensure_patched("argocd")

    assert patched is True
    written = mock_patch.call_args.args[2]
    assert some_key in written
    assert written[some_key] == desired[some_key]


@pytest.mark.asyncio
async def test_ensure_patched_handles_missing_configmap():
    with (
        patch("cluster_agent.k8s.get_configmap", AsyncMock(return_value=None)),
        patch("cluster_agent.k8s.patch_configmap", AsyncMock()) as mock_patch,
    ):
        patched = await argocd.ensure_patched("argocd")
    assert patched is True
    assert mock_patch.call_count == 1


@pytest.mark.asyncio
async def test_discover_reports_rbac_denied():
    with patch("cluster_agent.k8s.find_argocd", AsyncMock(side_effect=argocd.k8s.RBACDeniedError("nope"))):
        result = await argocd.discover()
    assert result["status"] == "rbac_denied"


@pytest.mark.asyncio
async def test_discover_not_found_when_no_deployment_matches():
    with patch("cluster_agent.k8s.find_argocd", AsyncMock(return_value=None)):
        result = await argocd.discover()
    assert result == {"status": "not_found", "version": None, "namespace": None}
