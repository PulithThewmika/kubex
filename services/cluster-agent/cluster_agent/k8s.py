"""Kubernetes API access for the cluster agent (E22-T3-S1/S3/S4/S5/S6).

Uses the official kubernetes python client (per #663's acceptance criteria)
with in-cluster config — this agent runs as a Pod *inside* the target
cluster via the install manifest's ServiceAccount (install.py's
build_install_manifest), unlike services/agent/agent/k8s_client.py's
raw-httpx approach, which reaches into a cluster from *outside* it with a
static long-lived token. Falls back to the local kubeconfig when there's no
in-cluster mount, so the same code path runs during local/CI testing
(#674).

The kubernetes client has no asyncio support — every call here is
synchronous and offloaded with asyncio.to_thread, the same pattern
services/ingest uses for bcrypt.
"""

from __future__ import annotations

import asyncio
import logging

from kubernetes import client, config
from kubernetes.client.rest import ApiException

logger = logging.getLogger("kubex.cluster_agent.k8s")

ARGOCD_NOTIFICATIONS_CM = "argocd-notifications-cm"


class RBACDeniedError(Exception):
    """A K8s API call was denied by RBAC (403)."""


_configured = False


def _ensure_config() -> None:
    global _configured
    if _configured:
        return
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
    _configured = True


def _apps_v1() -> client.AppsV1Api:
    _ensure_config()
    return client.AppsV1Api()


def _core_v1() -> client.CoreV1Api:
    _ensure_config()
    return client.CoreV1Api()


def _find_deployment_sync(name_substrings: tuple[str, ...]) -> tuple[str, str] | None:
    try:
        deployments = _apps_v1().list_deployment_for_all_namespaces()
    except ApiException as e:
        if e.status == 403:
            raise RBACDeniedError(str(e)) from e
        raise
    for dep in deployments.items:
        if any(sub in dep.metadata.name for sub in name_substrings):
            return dep.metadata.namespace, dep.metadata.name
    return None


def _find_service_sync(name_substrings: tuple[str, ...]) -> tuple[str, str] | None:
    try:
        services = _core_v1().list_service_for_all_namespaces()
    except ApiException as e:
        if e.status == 403:
            raise RBACDeniedError(str(e)) from e
        raise
    for svc in services.items:
        if any(sub in svc.metadata.name for sub in name_substrings):
            return svc.metadata.namespace, svc.metadata.name
    return None


def _get_deployment_sync(namespace: str, name: str):
    try:
        return _apps_v1().read_namespaced_deployment(name, namespace)
    except ApiException as e:
        if e.status == 403:
            raise RBACDeniedError(str(e)) from e
        if e.status == 404:
            return None
        raise


async def get_deployment(namespace: str, name: str):
    return await asyncio.to_thread(_get_deployment_sync, namespace, name)


async def find_argocd() -> tuple[str, str] | None:
    """Discover the argocd-server Deployment. Returns (namespace, name) or None."""
    return await asyncio.to_thread(_find_deployment_sync, ("argocd-server",))


async def find_prometheus() -> tuple[str, str] | None:
    """Discover a Prometheus Service. kube-prometheus-stack names it
    'prometheus-operated'; other common installs use 'prometheus-server'
    or 'prometheus-k8s'."""
    return await asyncio.to_thread(
        _find_service_sync, ("prometheus-operated", "prometheus-server", "prometheus-k8s")
    )


def _get_configmap_sync(namespace: str, name: str):
    try:
        return _core_v1().read_namespaced_config_map(name, namespace)
    except ApiException as e:
        if e.status == 403:
            raise RBACDeniedError(str(e)) from e
        if e.status == 404:
            return None
        raise


def _patch_configmap_sync(namespace: str, name: str, data: dict[str, str]) -> None:
    try:
        _core_v1().patch_namespaced_config_map(name, namespace, {"data": data})
    except ApiException as e:
        if e.status == 403:
            raise RBACDeniedError(str(e)) from e
        raise


async def get_configmap(namespace: str, name: str):
    return await asyncio.to_thread(_get_configmap_sync, namespace, name)


async def patch_configmap(namespace: str, name: str, data: dict[str, str]) -> None:
    await asyncio.to_thread(_patch_configmap_sync, namespace, name, data)
