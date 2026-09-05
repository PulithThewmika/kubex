import hashlib
import hmac
import logging
import os

from fastapi import Header, HTTPException, Request

logger = logging.getLogger("kubex.ingest.auth")

GITHUB_WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
ARGOCD_WEBHOOK_TOKEN = os.environ.get("ARGOCD_WEBHOOK_TOKEN", "")
ALERTMANAGER_WEBHOOK_TOKEN = os.environ.get("ALERTMANAGER_WEBHOOK_TOKEN", "")
GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
JWT_SECRET = os.environ.get("JWT_SECRET", "")


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
