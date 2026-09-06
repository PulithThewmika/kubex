"""ArgoCD discovery, version detection, and notifications ConfigMap patching
(E22-T3-S3/S4/S5/S9).

The webhook config merged into argocd-notifications-cm mirrors the local
dev pattern in deploy/argocd/notifications-cm.yaml (service.webhook.*,
template.*, trigger.*) but points at this cluster's own DEPLOYLENS_ENDPOINT
with its own CLUSTER_TOKEN instead of the single shared ARGOCD_WEBHOOK_TOKEN
that path uses — ingest's /webhooks/argocd route accepting per-cluster
bearer tokens is tracked as a follow-up (it currently only checks the one
global ARGOCD_WEBHOOK_TOKEN), out of scope for this task.

Keys are prefixed "deploylens-agent" (not "kubex") so a cluster that also
has the legacy single-tenant webhook configured doesn't collide with it.
"""

from __future__ import annotations

import logging

from . import k8s
from .config import DEPLOYLENS_ENDPOINT, CLUSTER_TOKEN

logger = logging.getLogger("kubex.cluster_agent.argocd")

_WEBHOOK_NAME = "deploylens-agent"
_EVENT_TYPES = ("on-sync-running", "on-sync-succeeded", "on-sync-failed")


def _webhook_body(event_type: str) -> str:
    return (
        "{\n"
        f'  "type": "{event_type}",\n'
        '  "app": {\n'
        '    "metadata": {"name": "{{.app.metadata.name}}"},\n'
        '    "status": {\n'
        '      "sync": {"status": "{{.app.status.sync.status}}", "revision": "{{.app.status.sync.revision}}"},\n'
        '      "health": {"status": "{{.app.status.health.status}}"},\n'
        '      "operationState": {\n'
        '        "phase": "{{.app.status.operationState.phase}}",\n'
        '        "message": "{{.app.status.operationState.message}}",\n'
        '        "syncResult": {"revision": "{{.app.status.operationState.syncResult.revision}}"}\n'
        "      },\n"
        '      "summary": {"images": "{{.app.status.summary.images}}"}\n'
        "    }\n"
        "  }\n"
        "}"
    )


def desired_notifications_data() -> dict[str, str]:
    """The ConfigMap keys this agent owns. Only these keys are ever
    written or compared — any keys another controller/user manages in the
    same ConfigMap are left untouched by the merge in ensure_patched()."""
    data = {
        f"service.webhook.{_WEBHOOK_NAME}": (
            f"url: {DEPLOYLENS_ENDPOINT}/webhooks/argocd\n"
            "headers:\n"
            "  - name: Authorization\n"
            f"    value: Bearer {CLUSTER_TOKEN}\n"
            "  - name: Content-Type\n"
            "    value: application/json\n"
        ),
    }
    for event_type in _EVENT_TYPES:
        data[f"template.{_WEBHOOK_NAME}-{event_type}"] = (
            f"webhook:\n  {_WEBHOOK_NAME}:\n    method: POST\n    body: |\n"
            + "\n".join(f"      {line}" for line in _webhook_body(event_type).splitlines())
            + "\n"
        )
    data[f"trigger.{_WEBHOOK_NAME}-on-sync-running"] = (
        f"- when: app.status.operationState.phase in ['Running']\n  send: [{_WEBHOOK_NAME}-on-sync-running]\n"
    )
    data[f"trigger.{_WEBHOOK_NAME}-on-sync-succeeded"] = (
        f"- when: app.status.operationState.phase in ['Succeeded']\n  send: [{_WEBHOOK_NAME}-on-sync-succeeded]\n"
    )
    data[f"trigger.{_WEBHOOK_NAME}-on-sync-failed"] = (
        f"- when: app.status.operationState.phase in ['Failed', 'Error']\n  send: [{_WEBHOOK_NAME}-on-sync-failed]\n"
    )
    return data


async def ensure_patched(namespace: str) -> bool:
    """Patch argocd-notifications-cm with this agent's webhook config if
    any of its keys are missing or stale. Returns True if a patch was made
    (idempotent: a re-run with nothing to change makes no API call)."""
    cm = await k8s.get_configmap(namespace, k8s.ARGOCD_NOTIFICATIONS_CM)
    existing = (cm.data or {}) if cm is not None else {}
    desired = desired_notifications_data()

    missing_or_stale = {k: v for k, v in desired.items() if existing.get(k) != v}
    if not missing_or_stale:
        return False

    await k8s.patch_configmap(namespace, k8s.ARGOCD_NOTIFICATIONS_CM, missing_or_stale)
    logger.info(
        "Patched %s/%s with %d webhook key(s)", namespace, k8s.ARGOCD_NOTIFICATIONS_CM, len(missing_or_stale)
    )
    return True


def _extract_version(image: str | None) -> str | None:
    if not image or ":" not in image:
        return None
    return image.rsplit(":", 1)[1]


async def discover() -> dict:
    """Discover ArgoCD and, if found and reachable, patch its notifications
    ConfigMap. Returns a dict shaped for the heartbeat payload:
    {status, version, namespace}."""
    try:
        found = await k8s.find_argocd()
    except k8s.RBACDeniedError:
        logger.warning("RBAC denied listing Deployments — cannot discover ArgoCD")
        return {"status": "rbac_denied", "version": None, "namespace": None}

    if found is None:
        return {"status": "not_found", "version": None, "namespace": None}

    namespace, name = found
    version = None
    try:
        dep = await k8s.get_deployment(namespace, name)
        containers = dep.spec.template.spec.containers if dep is not None else []
        if containers:
            version = _extract_version(containers[0].image)
    except k8s.RBACDeniedError:
        logger.warning("RBAC denied reading Deployment %s/%s for version detection", namespace, name)
    except Exception:
        logger.exception("Failed to read ArgoCD deployment image for version detection")

    try:
        await ensure_patched(namespace)
    except k8s.RBACDeniedError:
        logger.warning("RBAC denied patching %s in namespace %s", k8s.ARGOCD_NOTIFICATIONS_CM, namespace)
        return {"status": "rbac_denied", "version": version, "namespace": namespace}
    except Exception:
        logger.exception("Failed to patch ArgoCD notifications ConfigMap in namespace %s", namespace)
        return {"status": "found", "version": version, "namespace": namespace}

    return {"status": "found", "version": version, "namespace": namespace}
