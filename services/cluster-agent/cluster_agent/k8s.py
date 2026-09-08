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
from typing import Callable, TypeVar

from kubernetes import client, config
from kubernetes.client.rest import ApiException

logger = logging.getLogger("kubex.cluster_agent.k8s")

ARGOCD_NOTIFICATIONS_CM = "argocd-notifications-cm"
ARGOCD_NOTIFICATIONS_SECRET = "argocd-notifications-secret"

T = TypeVar("T")


class RBACDeniedError(Exception):
    """A K8s API call was denied by RBAC (403)."""


_configured = False
_apps_v1_client: client.AppsV1Api | None = None
_core_v1_client: client.CoreV1Api | None = None


def _ensure_config() -> None:
    global _configured
    if _configured:
        return
    try:
        config.load_incluster_config()
    except config.ConfigException:
        logger.warning(
            "No in-cluster ServiceAccount mount found — falling back to the local kubeconfig. "
            "Expected in local/CI runs, not in a deployed agent Pod."
        )
        config.load_kube_config()
    _configured = True


def _apps_v1() -> client.AppsV1Api:
    global _apps_v1_client
    _ensure_config()
    if _apps_v1_client is None:
        _apps_v1_client = client.AppsV1Api()
    return _apps_v1_client


def _core_v1() -> client.CoreV1Api:
    global _core_v1_client
    _ensure_config()
    if _core_v1_client is None:
        _core_v1_client = client.CoreV1Api()
    return _core_v1_client


def _call(fn: Callable[[], T], *, not_found_ok: bool = False) -> T | None:
    """Run one K8s API call, translating 403 -> RBACDeniedError (and, if
    not_found_ok, 404 -> None) in one place instead of at every call site."""
    try:
        return fn()
    except ApiException as e:
        if e.status == 403:
            raise RBACDeniedError(str(e)) from e
        if not_found_ok and e.status == 404:
            return None
        raise


def _find_deployment_sync(name_substrings: tuple[str, ...]) -> tuple[str, str] | None:
    deployments = _call(_apps_v1().list_deployment_for_all_namespaces)
    for dep in deployments.items:
        if any(sub in dep.metadata.name for sub in name_substrings):
            return dep.metadata.namespace, dep.metadata.name
    return None


def _find_service_sync(
    name_substrings: tuple[str, ...], exclude_substrings: tuple[str, ...] = (),
) -> tuple[str, str] | None:
    services = _call(_core_v1().list_service_for_all_namespaces)
    for svc in services.items:
        name = svc.metadata.name
        if any(sub in name for sub in name_substrings) and not any(ex in name for ex in exclude_substrings):
            return svc.metadata.namespace, name
    return None


def _get_deployment_sync(namespace: str, name: str) -> client.V1Deployment | None:
    return _call(lambda: _apps_v1().read_namespaced_deployment(name, namespace), not_found_ok=True)


async def get_deployment(namespace: str, name: str) -> client.V1Deployment | None:
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


async def find_loki() -> tuple[str, str] | None:
    """Discover a Loki Service (#840). Grafana's single-binary Helm chart
    names it 'loki'; distributed-mode installs commonly expose
    'loki-gateway'; the older loki-stack chart uses 'loki-stack'.

    Excludes 'canary'/'memberlist' — the standard Loki Helm chart's
    companion services (loki-canary: a synthetic-monitoring sidecar,
    loki-*-memberlist: gossip-ring discovery) both contain 'loki' as a
    substring and are not query-capable; matching one of them instead of
    the real Loki service silently breaks every relayed LogQL query
    (found in review, #840, before this ever shipped)."""
    return await asyncio.to_thread(
        _find_service_sync,
        ("loki-gateway", "loki-stack", "loki"),
        ("canary", "memberlist"),
    )


def _get_configmap_sync(namespace: str, name: str) -> client.V1ConfigMap | None:
    return _call(lambda: _core_v1().read_namespaced_config_map(name, namespace), not_found_ok=True)


def _patch_configmap_sync(namespace: str, name: str, data: dict[str, str]) -> None:
    _call(lambda: _core_v1().patch_namespaced_config_map(name, namespace, {"data": data}))


def _create_configmap_sync(namespace: str, name: str, data: dict[str, str]) -> None:
    body = client.V1ConfigMap(metadata=client.V1ObjectMeta(name=name, namespace=namespace), data=data)
    _call(lambda: _core_v1().create_namespaced_config_map(namespace, body))


async def get_configmap(namespace: str, name: str) -> client.V1ConfigMap | None:
    return await asyncio.to_thread(_get_configmap_sync, namespace, name)


async def patch_configmap(namespace: str, name: str, data: dict[str, str]) -> None:
    await asyncio.to_thread(_patch_configmap_sync, namespace, name, data)


async def create_configmap(namespace: str, name: str, data: dict[str, str]) -> None:
    await asyncio.to_thread(_create_configmap_sync, namespace, name, data)


def _get_secret_sync(namespace: str, name: str) -> client.V1Secret | None:
    return _call(lambda: _core_v1().read_namespaced_secret(name, namespace), not_found_ok=True)


def _patch_secret_sync(namespace: str, name: str, string_data: dict[str, str]) -> None:
    _call(lambda: _core_v1().patch_namespaced_secret(name, namespace, {"stringData": string_data}))


async def get_secret(namespace: str, name: str) -> client.V1Secret | None:
    return await asyncio.to_thread(_get_secret_sync, namespace, name)


async def patch_secret(namespace: str, name: str, string_data: dict[str, str]) -> None:
    await asyncio.to_thread(_patch_secret_sync, namespace, name, string_data)
