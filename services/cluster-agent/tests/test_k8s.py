from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from kubernetes.client.rest import ApiException

from cluster_agent import k8s


def test_find_deployment_raises_rbac_denied_on_403() -> None:
    api = MagicMock()
    api.list_deployment_for_all_namespaces.side_effect = ApiException(status=403)
    with patch("cluster_agent.k8s._apps_v1", return_value=api):
        with pytest.raises(k8s.RBACDeniedError):
            k8s._find_deployment_sync(("argocd-server",))


def test_find_deployment_returns_first_match() -> None:
    dep = MagicMock()
    dep.metadata.name = "argocd-server"
    dep.metadata.namespace = "argocd"
    api = MagicMock()
    api.list_deployment_for_all_namespaces.return_value = MagicMock(items=[dep])
    with patch("cluster_agent.k8s._apps_v1", return_value=api):
        result = k8s._find_deployment_sync(("argocd-server",))
    assert result == ("argocd", "argocd-server")


def test_find_service_sync_excludes_matching_auxiliary_services() -> None:
    """#840: loki-canary/loki-*-memberlist both contain 'loki' as a
    substring but aren't query-capable — the exclude list must keep them
    from being picked over (or instead of) the real Loki service."""
    canary = MagicMock()
    canary.metadata.name = "loki-canary"
    canary.metadata.namespace = "monitoring"
    real = MagicMock()
    real.metadata.name = "loki"
    real.metadata.namespace = "monitoring"
    api = MagicMock()
    api.list_service_for_all_namespaces.return_value = MagicMock(items=[canary, real])
    with patch("cluster_agent.k8s._core_v1", return_value=api):
        result = k8s._find_service_sync(("loki-gateway", "loki-stack", "loki"), ("canary", "memberlist"))
    assert result == ("monitoring", "loki")


def test_find_service_sync_returns_none_when_only_excluded_matches_exist() -> None:
    canary = MagicMock()
    canary.metadata.name = "loki-canary"
    canary.metadata.namespace = "monitoring"
    api = MagicMock()
    api.list_service_for_all_namespaces.return_value = MagicMock(items=[canary])
    with patch("cluster_agent.k8s._core_v1", return_value=api):
        result = k8s._find_service_sync(("loki",), ("canary", "memberlist"))
    assert result is None


def test_get_configmap_returns_none_on_404() -> None:
    api = MagicMock()
    api.read_namespaced_config_map.side_effect = ApiException(status=404)
    with patch("cluster_agent.k8s._core_v1", return_value=api):
        assert k8s._get_configmap_sync("argocd", "argocd-notifications-cm") is None


def test_patch_configmap_raises_rbac_denied_on_403() -> None:
    api = MagicMock()
    api.patch_namespaced_config_map.side_effect = ApiException(status=403)
    with patch("cluster_agent.k8s._core_v1", return_value=api):
        with pytest.raises(k8s.RBACDeniedError):
            k8s._patch_configmap_sync("argocd", "argocd-notifications-cm", {"a": "b"})
