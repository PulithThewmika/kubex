from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from kubernetes.client.rest import ApiException

from cluster_agent import k8s


def test_find_deployment_raises_rbac_denied_on_403():
    api = MagicMock()
    api.list_deployment_for_all_namespaces.side_effect = ApiException(status=403)
    with patch("cluster_agent.k8s._apps_v1", return_value=api):
        with pytest.raises(k8s.RBACDeniedError):
            k8s._find_deployment_sync(("argocd-server",))


def test_find_deployment_returns_first_match():
    dep = MagicMock()
    dep.metadata.name = "argocd-server"
    dep.metadata.namespace = "argocd"
    api = MagicMock()
    api.list_deployment_for_all_namespaces.return_value = MagicMock(items=[dep])
    with patch("cluster_agent.k8s._apps_v1", return_value=api):
        result = k8s._find_deployment_sync(("argocd-server",))
    assert result == ("argocd", "argocd-server")


def test_get_configmap_returns_none_on_404():
    api = MagicMock()
    api.read_namespaced_config_map.side_effect = ApiException(status=404)
    with patch("cluster_agent.k8s._core_v1", return_value=api):
        assert k8s._get_configmap_sync("argocd", "argocd-notifications-cm") is None


def test_patch_configmap_raises_rbac_denied_on_403():
    api = MagicMock()
    api.patch_namespaced_config_map.side_effect = ApiException(status=403)
    with patch("cluster_agent.k8s._core_v1", return_value=api):
        with pytest.raises(k8s.RBACDeniedError):
            k8s._patch_configmap_sync("argocd", "argocd-notifications-cm", {"a": "b"})
