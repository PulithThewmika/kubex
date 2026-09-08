import asyncio
import hashlib
import hmac
import logging
import os
import time
import uuid
from datetime import datetime, timezone

import bcrypt
from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_session
from .models.api_key import ApiKey
from .models.cluster import Cluster

logger = logging.getLogger("kubex.ingest.auth")

GITHUB_WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
GITHUB_APP_WEBHOOK_SECRET = os.environ.get("GITHUB_APP_WEBHOOK_SECRET", "")
ARGOCD_WEBHOOK_TOKEN = os.environ.get("ARGOCD_WEBHOOK_TOKEN", "")
ALERTMANAGER_WEBHOOK_TOKEN = os.environ.get("ALERTMANAGER_WEBHOOK_TOKEN", "")
# Shared bearer token for internal service-to-service calls (#840) — the
# same secret mcp_client.py already sends when ingest calls OUT to the MCP
# server (E20-T3). Reused here for the reverse direction: the MCP server
# calling IN to ingest's org-scoped telemetry relay
# (routers/relay_internal.py). One secret, one docstring, instead of a
# second env var with an identical trust model.
MCP_INTERNAL_TOKEN = os.environ.get("MCP_INTERNAL_TOKEN", "")
# Static bearer the Grafana Prometheus datasource sends to /api/prom. The
# org a query runs against travels in the PromQL itself (org_id="<uuid>",
# injected by the panel proxy from UserContext); this token is what makes
# that org id trustworthy — without it any container on the compose
# network could hit /api/prom and forge one.
GRAFANA_DATASOURCE_TOKEN = os.environ.get("GRAFANA_DATASOURCE_TOKEN", "")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET", "")
GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
JWT_SECRET = os.environ.get("JWT_SECRET", "")
# Where the OAuth callback sends the browser after login — the React
# shell's own origin, not this API's (it has no UI routes of its own).
SHELL_URL = os.environ.get("SHELL_URL", "http://localhost:5173")
# Externally reachable address of this ingest service, embedded into
# generated cluster-agent install manifests (E22-T2) so the agent knows
# where to phone home.
INGEST_PUBLIC_URL = os.environ.get("INGEST_PUBLIC_URL", "http://localhost:8000")
# The cluster bearer token travels over this URL on every agent request —
# cluster_agent/config.py already refuses a non-https DEPLOYLENS_ENDPOINT
# unless the agent's own ALLOW_INSECURE_ENDPOINT is set. This is the same
# escape hatch on the manifest-generation side, so a local/dev
# INGEST_PUBLIC_URL (e.g. http://host.docker.internal:8000 against a Kind
# cluster) doesn't need a real TLS cert just to test the install flow.
ALLOW_INSECURE_INGEST_PUBLIC_URL = os.environ.get("ALLOW_INSECURE_INGEST_PUBLIC_URL", "").lower() in ("1", "true")

# health_check_url (E23-T1) is pinged periodically by the always-on
# detection agent, so a loopback/link-local target lets an org member turn
# it into an SSRF probe against the agent's own host or cloud metadata
# (169.254.169.254) — same class of risk as INGEST_PUBLIC_URL above, same
# escape hatch for local/dev (e.g. pointing it at the compose network's
# ingest:8000 to test the feature itself).
ALLOW_INSECURE_HEALTH_CHECK_URL = os.environ.get("ALLOW_INSECURE_HEALTH_CHECK_URL", "").lower() in ("1", "true")


def validate_auth_tokens() -> None:
    """Reject startup if any webhook/OAuth auth secret is empty or unset."""
    missing = []
    if not GITHUB_WEBHOOK_SECRET:
        missing.append("GITHUB_WEBHOOK_SECRET")
    if not GITHUB_APP_WEBHOOK_SECRET:
        missing.append("GITHUB_APP_WEBHOOK_SECRET")
    if not ARGOCD_WEBHOOK_TOKEN:
        missing.append("ARGOCD_WEBHOOK_TOKEN")
    if not ALERTMANAGER_WEBHOOK_TOKEN:
        missing.append("ALERTMANAGER_WEBHOOK_TOKEN")
    if not GITHUB_CLIENT_ID:
        missing.append("GITHUB_CLIENT_ID")
    if not GITHUB_CLIENT_SECRET:
        missing.append("GITHUB_CLIENT_SECRET")
    if not JWT_SECRET:
        missing.append("JWT_SECRET")
    if not MCP_INTERNAL_TOKEN:
        missing.append("MCP_INTERNAL_TOKEN")
    if missing:
        raise RuntimeError(
            f"Webhook/OAuth auth secrets must not be empty: {', '.join(missing)}. "
            "Set them in .env before starting the service."
        )


async def _verify_hmac_signature(request: Request, secret: str) -> bytes:
    signature_header = request.headers.get("X-Hub-Signature-256")
    if not signature_header:
        raise HTTPException(status_code=401, detail="Missing X-Hub-Signature-256 header")

    body = await request.body()
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, signature_header):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    return body


SLACK_SIGNATURE_MAX_SKEW_SECONDS = 60 * 5


async def verify_slack_signature(request: Request) -> bytes:
    """Verify an inbound Slack Events API request (E23-T5).

    Slack signs ``v0:{timestamp}:{raw_body}`` with the app signing secret.
    Rejecting a stale timestamp blocks replay of a captured request.
    """
    if not SLACK_SIGNING_SECRET:
        raise HTTPException(status_code=503, detail="Slack integration is not configured")

    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    if not timestamp or not signature:
        raise HTTPException(status_code=401, detail="Missing Slack signature headers")
    try:
        skew = abs(time.time() - int(timestamp))
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Slack timestamp") from None
    if skew > SLACK_SIGNATURE_MAX_SKEW_SECONDS:
        raise HTTPException(status_code=401, detail="Stale Slack request")

    body = await request.body()
    basestring = b"v0:" + timestamp.encode() + b":" + body
    expected = "v0=" + hmac.new(SLACK_SIGNING_SECRET.encode(), basestring, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")
    return body


async def verify_github_signature(request: Request) -> bytes:
    return await _verify_hmac_signature(request, GITHUB_WEBHOOK_SECRET)


async def verify_github_app_signature(request: Request) -> bytes:
    return await _verify_hmac_signature(request, GITHUB_APP_WEBHOOK_SECRET)


async def verify_argocd_token(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> Cluster | None:
    """Accept either the legacy global ARGOCD_WEBHOOK_TOKEN (returns None —
    caller falls back to argocd_app-name-based org resolution) or a
    per-cluster agent token (returns that Cluster, whose org_id the caller
    should use directly). The global check runs first since it's a cheap
    constant-time compare; the bcrypt cluster walk only runs when it
    doesn't match, so the common legacy path pays no extra latency.

    Per-cluster tokens close a real cross-tenant bug (#found 2026-09-08):
    the legacy path resolves org_id by matching an existing services row's
    argocd_app name, which has no idea which org a *newly connected*
    cluster belongs to and silently misattributes its deployments to
    whichever org happened to register that app name first.
    """
    if authorization is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    expected = f"Bearer {ARGOCD_WEBHOOK_TOKEN}"
    if hmac.compare_digest(authorization, expected):
        return None
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid bearer token")
    token = authorization.removeprefix("Bearer ").encode()
    cluster = await find_cluster_by_token(token, session)
    if cluster is None:
        raise HTTPException(status_code=401, detail="Invalid bearer token")
    return cluster


async def verify_alertmanager_token(authorization: str | None = Header(default=None)):
    if authorization is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    expected = f"Bearer {ALERTMANAGER_WEBHOOK_TOKEN}"
    if not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Invalid bearer token")


async def verify_internal_token(authorization: str | None = Header(default=None)) -> None:
    """Authenticate an internal service-to-service caller (#840) — today,
    the MCP server calling ingest's org-scoped telemetry relay. Fails
    closed on an unset token (same as verify_grafana_datasource_token)
    rather than the ARGOCD/ALERTMANAGER checks' implicit behavior, since
    an empty MCP_INTERNAL_TOKEN would otherwise mean "compare against
    literal 'Bearer '" instead of an explicit "not configured" error.
    """
    if not MCP_INTERNAL_TOKEN:
        raise HTTPException(status_code=503, detail="Internal relay not configured")
    if authorization is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    expected = f"Bearer {MCP_INTERNAL_TOKEN}"
    if not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Invalid bearer token")


async def verify_grafana_datasource_token(authorization: str | None = Header(default=None)):
    if not GRAFANA_DATASOURCE_TOKEN:
        # Fail closed: an unset token must not mean "allow everyone".
        raise HTTPException(status_code=503, detail="Datasource relay not configured")
    if authorization is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    expected = f"Bearer {GRAFANA_DATASOURCE_TOKEN}"
    if not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Invalid bearer token")


async def verify_api_key(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> uuid.UUID:
    """Validate a generic API key (E19-T4) and return its org_id.

    bcrypt hashes can't be looked up by index, so this checks the token
    against every stored hash. O(n) in the number of API keys
    system-wide — fine at this project's scale.
    """
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = authorization.removeprefix("Bearer ").encode()

    result = await session.execute(select(ApiKey))
    for key in result.scalars().all():
        # bcrypt.checkpw is CPU-bound and has no async form — running it
        # inline would block the event loop for every other in-flight
        # request on this worker.
        if await asyncio.to_thread(bcrypt.checkpw, token, key.token_hash.encode()):
            try:
                key.last_used = datetime.now(timezone.utc)
                await session.commit()
            except Exception:
                logger.warning("Failed to update last_used for api key %s", key.id)
                await session.rollback()
            return key.org_id

    raise HTTPException(status_code=401, detail="Invalid API key")


async def find_cluster_by_token(token: bytes, session: AsyncSession, *, allow_grace: bool = True) -> Cluster | None:
    """Same O(n) bcrypt-walk as verify_api_key. Each cluster also gets a
    second check against token_hash_old while its rotation grace period
    (E22-T1-S10) hasn't expired, so an agent that hasn't picked up a
    freshly rotated token yet still authenticates for up to 10 minutes.

    Shared by verify_cluster_token (bearer header) and the install-manifest
    endpoint (E22-T2, token in the URL path) so both paths stay in sync.
    allow_grace=False skips the token_hash_old check — the install endpoint
    uses this, since a grace-period token embedded in a generated manifest
    would go stale within the 10-minute window rather than at request time.
    """
    result = await session.execute(select(Cluster))
    now = datetime.now(timezone.utc)
    for cluster in result.scalars().all():
        if await asyncio.to_thread(bcrypt.checkpw, token, cluster.token_hash.encode()):
            return cluster
        if (
            allow_grace
            and cluster.token_hash_old
            and cluster.token_old_expires_at
            and cluster.token_old_expires_at > now
            and await asyncio.to_thread(bcrypt.checkpw, token, cluster.token_hash_old.encode())
        ):
            return cluster
    return None


async def verify_cluster_token(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> Cluster:
    """Authenticate a remote cluster agent (E22-T1) and return its Cluster row."""
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = authorization.removeprefix("Bearer ").encode()

    cluster = await find_cluster_by_token(token, session)
    if cluster is None:
        raise HTTPException(status_code=401, detail="Invalid cluster token")
    return cluster
