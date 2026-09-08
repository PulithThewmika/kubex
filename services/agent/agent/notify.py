"""Client for ingest's /internal/notify — the agent's only path to Slack.

The agent has no Slack integration of its own (no OAuth tokens, no
notification_channels access) — ingest owns all of that. This module just
asks ingest to deliver, and never treats a delivery failure as fatal:
firing/resolving the alert in Postgres (and to Alertmanager) is the part
that must succeed; Slack delivery is a best-effort extra on top, same as
the existing Alertmanager POST in alerting.py.
"""

from __future__ import annotations

import logging

import httpx

from .config import INGEST_URL, MCP_INTERNAL_TOKEN

logger = logging.getLogger("kubex.agent.notify")

_client: httpx.AsyncClient | None = None


def get_notify_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(base_url=INGEST_URL, timeout=10.0)
    return _client


async def close_notify_client() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        _client = None


async def notify_slack(org_id, event_type: str, text: str, service_id: int | None = None) -> None:
    """Best-effort — logs and returns on any failure, never raises."""
    client = get_notify_client()
    try:
        resp = await client.post(
            "/internal/notify",
            json={"org_id": str(org_id), "event_type": event_type, "text": text, "service_id": service_id},
            headers={"Authorization": f"Bearer {MCP_INTERNAL_TOKEN}"},
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("status") == "ok":
            logger.info("Slack notify delivered to %s", body.get("delivered_to"))
        elif body.get("status") == "skipped":
            logger.debug("Slack notify skipped: %s", body.get("reason"))
        else:
            logger.warning("Slack notify failed: %s", body)
    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
        logger.warning("Failed to reach ingest for Slack notify: %s", e)
