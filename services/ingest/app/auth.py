import asyncio
import hashlib
import hmac
import logging
import os
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


async def verify_github_signature(request: Request) -> bytes:
    return await _verify_hmac_signature(request, GITHUB_WEBHOOK_SECRET)


async def verify_github_app_signature(request: Request) -> bytes:
    return await _verify_hmac_signature(request, GITHUB_APP_WEBHOOK_SECRET)


async def verify_argocd_token(authorization: str | None = Header(default=None)):
    if authorization is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    expected = f"Bearer {ARGOCD_WEBHOOK_TOKEN}"
    if not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Invalid bearer token")


async def verify_alertmanager_token(authorization: str | None = Header(default=None)):
    if authorization is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    expected = f"Bearer {ALERTMANAGER_WEBHOOK_TOKEN}"
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


async def find_cluster_by_token(token: bytes, session: AsyncSession) -> Cluster | None:
    """Same O(n) bcrypt-walk as verify_api_key. Each cluster also gets a
    second check against token_hash_old while its rotation grace period
    (E22-T1-S10) hasn't expired, so an agent that hasn't picked up a
    freshly rotated token yet still authenticates for up to 10 minutes.

    Shared by verify_cluster_token (bearer header) and the install-manifest
    endpoint (E22-T2, token in the URL path) so both paths stay in sync.
    """
    result = await session.execute(select(Cluster))
    now = datetime.now(timezone.utc)
    for cluster in result.scalars().all():
        if await asyncio.to_thread(bcrypt.checkpw, token, cluster.token_hash.encode()):
            return cluster
        if (
            cluster.token_hash_old
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
