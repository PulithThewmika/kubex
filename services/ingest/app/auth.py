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

logger = logging.getLogger("kubex.ingest.auth")

GITHUB_WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
ARGOCD_WEBHOOK_TOKEN = os.environ.get("ARGOCD_WEBHOOK_TOKEN", "")
ALERTMANAGER_WEBHOOK_TOKEN = os.environ.get("ALERTMANAGER_WEBHOOK_TOKEN", "")
GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
JWT_SECRET = os.environ.get("JWT_SECRET", "")
# Where the OAuth callback sends the browser after login — the React
# shell's own origin, not this API's (it has no UI routes of its own).
SHELL_URL = os.environ.get("SHELL_URL", "http://localhost:5173")


def validate_auth_tokens() -> None:
    """Reject startup if any webhook/OAuth auth secret is empty or unset."""
    missing = []
    if not GITHUB_WEBHOOK_SECRET:
        missing.append("GITHUB_WEBHOOK_SECRET")
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


async def verify_github_signature(request: Request):
    signature_header = request.headers.get("X-Hub-Signature-256")
    if not signature_header:
        raise HTTPException(status_code=401, detail="Missing X-Hub-Signature-256 header")

    body = await request.body()
    expected = "sha256=" + hmac.new(
        GITHUB_WEBHOOK_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, signature_header):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    return body


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
        if bcrypt.checkpw(token, key.token_hash.encode()):
            try:
                key.last_used = datetime.now(timezone.utc)
                await session.commit()
            except Exception:
                logger.warning("Failed to update last_used for api key %s", key.id)
                await session.rollback()
            return key.org_id

    raise HTTPException(status_code=401, detail="Invalid API key")
