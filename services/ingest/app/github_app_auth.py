"""GitHub App JWT signing and per-installation access tokens (E21-T3-S1).

GitHub App auth is two-hop: sign a short-lived JWT with the App's private
key (proves "I am this App"), then exchange it for a per-installation
access token (proves "acting on behalf of this installation") — the
token actually used against the GitHub REST API. Installation tokens
expire after an hour, so callers go through `get_installation_token`
rather than caching the token themselves.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timezone

import httpx
import jwt

logger = logging.getLogger("kubex.github_app_auth")

GITHUB_APP_ID = os.environ.get("GITHUB_APP_ID", "")
GITHUB_APP_PRIVATE_KEY_PATH = os.environ.get("GITHUB_APP_PRIVATE_KEY_PATH", "")
GITHUB_API_URL = "https://api.github.com"

# ponytail: plain module-level dict, correct only for a single ingest
# process (this service runs as one uvicorn worker per docker-compose) —
# upgrade to a shared cache (Redis) if ingest ever runs multiple
# workers/replicas, since each would refetch independently otherwise.
_token_cache: dict[int, tuple[str, float]] = {}


def _read_private_key() -> str | None:
    if not GITHUB_APP_PRIVATE_KEY_PATH:
        return None
    with open(GITHUB_APP_PRIVATE_KEY_PATH) as f:
        return f.read()


def _generate_app_jwt() -> str | None:
    """Sign a JWT identifying the GitHub App itself (not an installation).

    Returns None if the App isn't configured, the key file can't be read,
    or it isn't a valid RS256 signing key — callers treat that as "no App
    auth available" and fall back to whatever static token they had
    before EPIC-021.
    """
    try:
        private_key = _read_private_key()
    except OSError as e:
        logger.warning("Failed to read GITHUB_APP_PRIVATE_KEY_PATH=%s: %s", GITHUB_APP_PRIVATE_KEY_PATH, e)
        return None
    if not private_key or not GITHUB_APP_ID:
        return None
    now = int(time.time())
    payload = {
        "iat": now - 60,  # backdate for clock drift, per GitHub's docs
        "exp": now + 600,  # GitHub caps this JWT's lifetime at 10 minutes
        "iss": GITHUB_APP_ID,
    }
    try:
        return jwt.encode(payload, private_key, algorithm="RS256")
    except (jwt.PyJWTError, ValueError, TypeError) as e:
        logger.warning("Failed to sign GitHub App JWT (malformed private key?): %s", e)
        return None


async def get_installation_token(github_installation_id: int) -> str | None:
    """Return a cached or freshly-exchanged installation access token.

    Returns None if the App isn't configured or the exchange fails —
    never raises, since this is a best-effort enhancement over a static
    token, not a hard dependency.
    """
    cached = _token_cache.get(github_installation_id)
    if cached is not None:
        token, expires_at = cached
        # Refresh a bit before actual expiry so a request doesn't start
        # with a token that dies mid-flight.
        if expires_at - time.time() > 60:
            return token

    # File I/O (_read_private_key) and RSA signing (jwt.encode RS256) are
    # both blocking/CPU-bound — offload them like auth.py already does for
    # bcrypt.checkpw, so this doesn't stall the event loop for every other
    # in-flight request on this worker.
    app_jwt = await asyncio.to_thread(_generate_app_jwt)
    if app_jwt is None:
        return None

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{GITHUB_API_URL}/app/installations/{github_installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": "application/vnd.github+json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            token = data["token"]
            expires_at = (
                datetime.strptime(data["expires_at"], "%Y-%m-%dT%H:%M:%SZ")
                .replace(tzinfo=timezone.utc)
                .timestamp()
            )
    except (httpx.HTTPError, ValueError, KeyError) as e:
        logger.warning(
            "Failed to exchange installation access token for installation_id=%s: %s",
            github_installation_id, e,
        )
        return None

    _token_cache[github_installation_id] = (token, expires_at)
    logger.info(
        "Exchanged installation access token for installation_id=%s (expires %s)",
        github_installation_id, data["expires_at"],
    )
    return token
