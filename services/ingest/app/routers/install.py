"""Cluster-agent install-manifest generator (EPIC-022 / E22-T2).

Unauthenticated by design — it's curl'd directly, before any agent (and
therefore any session) exists. The URL token IS the cluster's real E22-T1
bearer credential (shown once at POST /api/clusters time); this endpoint
looks it up the same way verify_cluster_token does and embeds it as-is into
the generated Secret, matching how Rancher/Weave-style agent installers
work. The response never distinguishes "bad token" from "unknown cluster"
(both 404) and isn't cached, so it can't be used to enumerate clusters.
"""

from __future__ import annotations

from ipaddress import ip_address
from urllib.parse import urlparse

import yaml
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import ALLOW_INSECURE_INGEST_PUBLIC_URL, INGEST_PUBLIC_URL, find_cluster_by_token
from ..auth_middleware import UserContext, get_current_user
from ..db import get_session
from ..schemas.cluster import InstallInfoResponse

_NO_STORE = {"Cache-Control": "no-store"}


def _is_loopback(host: str | None) -> bool:
    if host is None:
        return False
    if host == "localhost":
        return True
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


def _reject_unreachable_ingest_public_url() -> None:
    """Shared by install_manifest and install_info — both embed
    INGEST_PUBLIC_URL into something the agent uses to phone home, so both
    need the same two guards: a loopback URL would deploy an agent that
    phones home to itself, and a non-https URL sends the cluster's real
    bearer token in plaintext on every request (the same rule
    cluster_agent/config.py already enforces agent-side, with the same
    ALLOW_INSECURE_* escape hatch for local/dev testing)."""
    parsed = urlparse(INGEST_PUBLIC_URL)
    if parsed.hostname is None or _is_loopback(parsed.hostname):
        raise HTTPException(
            status_code=500,
            detail="INGEST_PUBLIC_URL is not configured to an externally reachable address",
            headers=_NO_STORE,
        )
    if parsed.scheme != "https" and not ALLOW_INSECURE_INGEST_PUBLIC_URL:
        raise HTTPException(
            status_code=500,
            detail="INGEST_PUBLIC_URL must be https:// — set ALLOW_INSECURE_INGEST_PUBLIC_URL=true for local/dev only",
            headers=_NO_STORE,
        )


router = APIRouter(tags=["install"])

# ponytail: :latest still contradicts CLAUDE.md's "images tagged with short
# SHA, never latest" convention. #681 (.github/workflows/agent.yml) now
# builds and pushes ghcr.io/puliththewmika/kubex-cluster-agent on every
# push to main/dev, tagged with both the short SHA and a branch-name
# floating tag (main -> :latest) — this endpoint has no way to know which
# SHA a given customer install should pin to, so it still hands out the
# floating tag. Upgrade path: track the last-known-good SHA per KubeX
# release and interpolate it here instead of :latest.
AGENT_IMAGE = "ghcr.io/puliththewmika/kubex-cluster-agent:latest"
AGENT_NAMESPACE = "kubex-agent"
# Matches deploy/argocd/cluster-agent.yaml's own repoURL/path — kept here
# too (not just there) so /api/install-info (E22-T5, #806) has a single
# place to read them from for the Add Cluster wizard's Helm/GitOps tabs.
CHART_REPO_URL = "https://github.com/PulithThewmika/kubex.git"
CHART_PATH = "deploy/helm/cluster-agent"


def build_install_manifest(token: str, endpoint: str) -> str:
    namespace = {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {"name": AGENT_NAMESPACE},
    }
    service_account = {
        "apiVersion": "v1",
        "kind": "ServiceAccount",
        "metadata": {"name": "kubex-agent", "namespace": AGENT_NAMESPACE},
    }
    cluster_role = {
        "apiVersion": "rbac.authorization.k8s.io/v1",
        "kind": "ClusterRole",
        "metadata": {"name": "kubex-agent"},
        "rules": [
            # ponytail: configmaps access is cluster-wide rather than
            # scoped to the argocd namespace as the issue names — scoping
            # it needs a namespaced Role+RoleBinding the agent provisions
            # itself once it discovers the ArgoCD namespace at runtime
            # (the namespace isn't known yet when this manifest is
            # generated, so it can't be baked in upfront). "watch" dropped
            # (security review, E22-T3): the agent only ever get/patches
            # this ConfigMap. "create" added (bug found in review,
            # E22-T3): a fresh ArgoCD install may not ship
            # argocd-notifications-cm yet, and PATCH 404s on a ConfigMap
            # that doesn't exist. Flagged, not silently accepted: "create"
            # is a genuine (if incremental) widening of an already-broad
            # grant — it lets a compromised agent Pod create new
            # ConfigMaps anywhere, not just modify existing ones. Track
            # the namespaced Role/RoleBinding fix as its own follow-up
            # task rather than attempting it here — it needs the agent to
            # also safely create Roles/RoleBindings, which is its own
            # privilege-escalation-adjacent design question.
            {"apiGroups": [""], "resources": ["configmaps"], "verbs": ["get", "list", "create", "patch"]},
            # "endpoints" dropped (security review, E22-T3): unused by any
            # agent code path — Prometheus discovery only lists Services.
            {"apiGroups": [""], "resources": ["services"], "verbs": ["get", "list"]},
            # E22-T3's ArgoCD/Prometheus discovery (S3/S6) scans Deployments
            # cluster-wide for argocd-server — missing from #660's original
            # rule set, added here since the agent can't function without it.
            {"apiGroups": ["apps"], "resources": ["deployments"], "verbs": ["get", "list"]},
            # Scoped by resourceNames to exactly one Secret (not a blanket
            # cluster-wide Secrets grant, which would be a far bigger blast
            # radius than the ConfigMap token exposure this exists to fix):
            # argocd.py patches the cluster's own bearer token into
            # argocd-notifications-secret rather than the plaintext
            # argocd-notifications-cm, per ArgoCD Notifications' documented
            # $secret-key interpolation syntax.
            # ponytail: no "create" verb here deliberately — K8s RBAC's
            # resourceNames restriction has no effect on "create" (the
            # object doesn't exist yet to name), so granting it would
            # actually mean "create a Secret with ANY name", undoing the
            # whole point of scoping this rule. If argocd-notifications-
            # secret doesn't already exist, argocd.py reports patch_failed
            # with a clear log message rather than silently getting a
            # cluster-wide Secrets-create grant to work around it. Fix
            # properly with a namespaced Role+RoleBinding once the
            # namespace is known (same gap as the ConfigMap scoping note
            # above), which supports "create" safely because it's already
            # namespace-scoped.
            {
                "apiGroups": [""],
                "resources": ["secrets"],
                "resourceNames": ["argocd-notifications-secret"],
                "verbs": ["get", "patch"],
            },
        ],
    }
    cluster_role_binding = {
        "apiVersion": "rbac.authorization.k8s.io/v1",
        "kind": "ClusterRoleBinding",
        "metadata": {"name": "kubex-agent"},
        "roleRef": {
            "apiGroup": "rbac.authorization.k8s.io",
            "kind": "ClusterRole",
            "name": "kubex-agent",
        },
        "subjects": [{"kind": "ServiceAccount", "name": "kubex-agent", "namespace": AGENT_NAMESPACE}],
    }
    secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": "kubex-agent-token", "namespace": AGENT_NAMESPACE},
        "type": "Opaque",
        "stringData": {"CLUSTER_TOKEN": token},
    }
    deployment = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": "kubex-agent", "namespace": AGENT_NAMESPACE},
        "spec": {
            "replicas": 1,
            "selector": {"matchLabels": {"app": "kubex-agent"}},
            "template": {
                "metadata": {"labels": {"app": "kubex-agent"}},
                "spec": {
                    "serviceAccountName": "kubex-agent",
                    "containers": [
                        {
                            "name": "kubex-agent",
                            "image": AGENT_IMAGE,
                            "env": [
                                {"name": "DEPLOYLENS_ENDPOINT", "value": endpoint},
                                {
                                    "name": "CLUSTER_TOKEN",
                                    "valueFrom": {
                                        "secretKeyRef": {"name": "kubex-agent-token", "key": "CLUSTER_TOKEN"}
                                    },
                                },
                            ],
                        }
                    ],
                },
            },
        },
    }

    documents = [namespace, service_account, cluster_role, cluster_role_binding, secret, deployment]
    return yaml.safe_dump_all(documents, sort_keys=False)


@router.get("/install/{token}.yaml", response_class=PlainTextResponse)
async def install_manifest(token: str, session: AsyncSession = Depends(get_session)) -> PlainTextResponse:
    _reject_unreachable_ingest_public_url()

    # allow_grace=False: a token accepted only via the post-rotation grace
    # window would go stale ~10 minutes after this manifest is applied,
    # with no indication of that in the generated Secret. Reject it here
    # and make the caller re-fetch with the current token instead.
    cluster = await find_cluster_by_token(token.encode(), session, allow_grace=False)
    if cluster is None:
        raise HTTPException(status_code=404, detail="Not found", headers=_NO_STORE)

    manifest = build_install_manifest(token, INGEST_PUBLIC_URL)
    return PlainTextResponse(manifest, media_type="application/yaml", headers=_NO_STORE)


@router.get("/api/install-info", response_model=InstallInfoResponse)
async def install_info(user: UserContext = Depends(get_current_user)) -> InstallInfoResponse:
    """Authoritative values for the Add Cluster wizard's Helm/GitOps command
    text (E22-T5, #806) — the frontend used to hand-duplicate AGENT_NAMESPACE/
    the chart repo path as string literals, which could silently drift from
    this file's own values. No secrets here (token stays client-side, from
    POST /api/clusters), so `user` is unused beyond requiring a session."""
    del user
    _reject_unreachable_ingest_public_url()
    return InstallInfoResponse(
        ingest_public_url=INGEST_PUBLIC_URL,
        agent_namespace=AGENT_NAMESPACE,
        chart_repo_url=CHART_REPO_URL,
        chart_path=CHART_PATH,
    )
