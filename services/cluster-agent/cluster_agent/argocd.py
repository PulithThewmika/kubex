"""ArgoCD discovery, version detection, and notifications ConfigMap/Secret
patching (E22-T3-S3/S4/S5/S9).

The webhook config merged into argocd-notifications-cm mirrors the local
dev pattern in deploy/argocd/notifications-cm.yaml (service.webhook.*,
template.*, trigger.*) but points at this cluster's own DEPLOYLENS_ENDPOINT
instead of the single shared ARGOCD_WEBHOOK_TOKEN that path uses — ingest's
/webhooks/argocd route accepting per-cluster bearer tokens is tracked as a
follow-up (it currently only checks the one global ARGOCD_WEBHOOK_TOKEN),
out of scope for this task.

The cluster's own bearer token is written into argocd-notifications-secret
and referenced from the ConfigMap via ArgoCD Notifications' documented
$secret-key interpolation (never embedded directly in the ConfigMap, which
is far more commonly readable — e.g. by ArgoCD's own UI, or by any RBAC
grant that includes ConfigMaps but not Secrets — than the Secret it lives
in) (security review, E22-T3).

Keys are prefixed "deploylens-agent" (not "kubex") so a cluster that also
has the legacy single-tenant webhook configured doesn't collide with it.
"""

from __future__ import annotations

import base64
import logging

from . import k8s
from .config import DEPLOYLENS_ENDPOINT, CLUSTER_TOKEN

logger = logging.getLogger("kubex.cluster_agent.argocd")

_WEBHOOK_NAME = "deploylens-agent"
_SECRET_KEY = f"{_WEBHOOK_NAME}-token"
_EVENT_TYPES = ("on-sync-running", "on-sync-succeeded", "on-sync-failed")


def _webhook_body(event_type: str) -> str:
    # Every dynamic value goes through {{toJson ...}}, not bare
    # interpolation — ArgoCD's documented safe pattern for building a JSON
    # webhook body. sync/health status and phase are normally enum-like,
    # but operationState.message and summary.images are free text from Git
    # history and Helm/Kustomize error output that can contain quotes,
    # backslashes, or newlines; bare interpolation of any of these fields
    # would let such a value break the JSON structure or inject sibling
    # keys (security review, E22-T3).
    return (
        "{\n"
        f'  "type": "{event_type}",\n'  # event_type is one of _EVENT_TYPES, a fixed internal constant, not untrusted
        '  "app": {\n'
        '    "metadata": {"name": {{toJson .app.metadata.name}}},\n'
        '    "status": {\n'
        '      "sync": {"status": {{toJson .app.status.sync.status}}, "revision": {{toJson .app.status.sync.revision}}},\n'
        '      "health": {"status": {{toJson .app.status.health.status}}},\n'
        '      "operationState": {\n'
        '        "phase": {{toJson .app.status.operationState.phase}},\n'
        '        "message": {{toJson .app.status.operationState.message}},\n'
        '        "syncResult": {"revision": {{toJson .app.status.operationState.syncResult.revision}}}\n'
        "      },\n"
        '      "summary": {"images": {{toJson .app.status.summary.images}}}\n'
        "    }\n"
        "  }\n"
        "}"
    )


def desired_notifications_secret_data() -> dict[str, str]:
    """The Secret key this agent owns, referenced from the ConfigMap via
    ArgoCD's $key interpolation instead of embedding the token directly."""
    return {_SECRET_KEY: CLUSTER_TOKEN}


def desired_notifications_data() -> dict[str, str]:
    """The ConfigMap keys this agent owns. Only these keys are ever
    written or compared — any keys another controller/user manages in the
    same ConfigMap are left untouched by the merge in ensure_patched()."""
    data = {
        f"service.webhook.{_WEBHOOK_NAME}": (
            f"url: {DEPLOYLENS_ENDPOINT}/webhooks/argocd\n"
            "headers:\n"
            "  - name: Authorization\n"
            f"    value: Bearer ${_SECRET_KEY}\n"
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


def _decode_secret_data(secret) -> dict[str, str]:
    if secret is None or secret.data is None:
        return {}
    return {k: base64.b64decode(v).decode() for k, v in secret.data.items()}


async def _ensure_secret_patched(namespace: str) -> bool:
    secret = await k8s.get_secret(namespace, k8s.ARGOCD_NOTIFICATIONS_SECRET)
    desired = desired_notifications_secret_data()

    if secret is None:
        # Deliberately not created here: the RBAC rule for this Secret is
        # scoped by resourceNames to exactly "argocd-notifications-secret"
        # (see install.py), and K8s RBAC's resourceNames restriction does
        # not apply to "create" — granting create would mean "create a
        # Secret with any name", undoing the whole point of that scoping.
        # A fresh ArgoCD install nearly always ships with this Secret
        # already (it's part of the standard manifests); if it's genuinely
        # missing, that's an operator setup gap this agent can't safely
        # self-heal without a much bigger RBAC grant.
        raise RuntimeError(
            f"{k8s.ARGOCD_NOTIFICATIONS_SECRET} does not exist in namespace {namespace!r} — "
            "create it (see deploy/argocd/notifications-secret.yaml) before this agent can install its webhook."
        )

    existing = _decode_secret_data(secret)
    missing_or_stale = {k: v for k, v in desired.items() if existing.get(k) != v}
    if not missing_or_stale:
        return False

    await k8s.patch_secret(namespace, k8s.ARGOCD_NOTIFICATIONS_SECRET, missing_or_stale)
    logger.info("Patched %s/%s with the cluster token", namespace, k8s.ARGOCD_NOTIFICATIONS_SECRET)
    return True


async def ensure_patched(namespace: str) -> bool:
    """Patch (or create, if absent) argocd-notifications-cm/-secret with
    this agent's webhook config if any of their keys are missing or stale.
    Returns True if a write was made to either (idempotent: a re-run with
    nothing to change makes no API call)."""
    secret_patched = await _ensure_secret_patched(namespace)

    cm = await k8s.get_configmap(namespace, k8s.ARGOCD_NOTIFICATIONS_CM)
    desired = desired_notifications_data()

    if cm is None:
        # Same 404-on-PATCH issue as the Secret above: a fresh ArgoCD
        # install may not have a notifications ConfigMap yet either.
        await k8s.create_configmap(namespace, k8s.ARGOCD_NOTIFICATIONS_CM, desired)
        logger.info("Created %s/%s with %d webhook key(s)", namespace, k8s.ARGOCD_NOTIFICATIONS_CM, len(desired))
        return True

    existing = cm.data or {}
    missing_or_stale = {k: v for k, v in desired.items() if existing.get(k) != v}
    if not missing_or_stale:
        return secret_patched

    await k8s.patch_configmap(namespace, k8s.ARGOCD_NOTIFICATIONS_CM, missing_or_stale)
    logger.info(
        "Patched %s/%s with %d webhook key(s)", namespace, k8s.ARGOCD_NOTIFICATIONS_CM, len(missing_or_stale)
    )
    return True


def _extract_version(image: str | None) -> str | None:
    """Best-effort tag extraction from a container image reference.
    Handles a plain tag ("argocd:v2.9.3" -> "v2.9.3"), a digest-pinned
    image with no tag ("argocd@sha256:..." -> None, not the digest), and a
    registry host:port with no tag ("registry.internal:5000/argocd" ->
    None, not "5000/argocd") — a bare rsplit(":", 1) on the whole
    reference mishandles both of the latter two (bug found in review,
    E22-T3)."""
    if not image:
        return None
    image_without_digest = image.split("@", 1)[0]
    last_segment = image_without_digest.rsplit("/", 1)[-1]
    if ":" not in last_segment:
        return None
    return last_segment.rsplit(":", 1)[1]


async def discover() -> dict:
    """Discover ArgoCD and, if found and reachable, patch its notifications
    ConfigMap. Returns a dict shaped for the heartbeat payload:
    {status, version, namespace}."""
    try:
        found = await k8s.find_argocd()
    except k8s.RBACDeniedError:
        logger.warning("RBAC denied listing Deployments — cannot discover ArgoCD")
        return {"status": "rbac_denied", "version": None, "namespace": None}
    except Exception:
        # A non-RBAC K8s API error (expired token, 5xx) must not crash
        # bootstrap()/the self-heal loop the way an uncaught exception
        # would (bug found in review, E22-T3) — report it the same way
        # every other discovery failure is reported.
        logger.exception("Unexpected error discovering ArgoCD")
        return {"status": "error", "version": None, "namespace": None}

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
        # Not masked as "found" (bug found in review, E22-T3): a real,
        # non-RBAC failure here means the webhook never got installed, and
        # the heartbeat needs to say so rather than look identical to
        # success.
        logger.exception("Failed to patch ArgoCD notifications ConfigMap in namespace %s", namespace)
        return {"status": "patch_failed", "version": version, "namespace": namespace}

    return {"status": "found", "version": version, "namespace": namespace}
