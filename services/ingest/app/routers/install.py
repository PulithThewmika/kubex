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

from urllib.parse import urlparse

import yaml
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import INGEST_PUBLIC_URL, find_cluster_by_token
from ..db import get_session

_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}

router = APIRouter(tags=["install"])

# ponytail: :latest contradicts CLAUDE.md's "images tagged with short SHA,
# never latest" convention, but matches #660's literal acceptance criteria
# and there's no agent CI pipeline yet (E22-T3) to pin a real SHA against.
# Switch to a pinned tag once the agent has a build/publish workflow.
AGENT_IMAGE = "ghcr.io/puliththewmika/deploylens-agent:latest"
AGENT_NAMESPACE = "kubex-agent"


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
            # it would need a namespaced Role+RoleBinding in addition to
            # this ClusterRole, which #658's fixed resource list doesn't
            # include. Tighten with a Role/RoleBinding pair if that gap
            # matters before this ships to real clusters.
            {"apiGroups": [""], "resources": ["configmaps"], "verbs": ["get", "list", "watch", "patch"]},
            {"apiGroups": [""], "resources": ["services", "endpoints"], "verbs": ["get", "list"]},
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
    # A loopback INGEST_PUBLIC_URL (unset, or left at its localhost default)
    # would deploy an agent that phones home to itself instead of this
    # service — fail loudly rather than hand out a manifest that can never
    # connect.
    if urlparse(INGEST_PUBLIC_URL).hostname in _LOOPBACK_HOSTS:
        raise HTTPException(
            status_code=500,
            detail="INGEST_PUBLIC_URL is not configured to an externally reachable address",
        )

    # allow_grace=False: a token accepted only via the post-rotation grace
    # window would go stale ~10 minutes after this manifest is applied,
    # with no indication of that in the generated Secret. Reject it here
    # and make the caller re-fetch with the current token instead.
    cluster = await find_cluster_by_token(token.encode(), session, allow_grace=False)
    if cluster is None:
        raise HTTPException(status_code=404, detail="Not found")

    manifest = build_install_manifest(token, INGEST_PUBLIC_URL)
    return PlainTextResponse(manifest, media_type="application/yaml", headers={"Cache-Control": "no-store"})
