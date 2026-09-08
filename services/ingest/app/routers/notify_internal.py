"""Internal event -> Slack delivery endpoint.

The detection agent (a separate Python process/container) fires and
resolves alerts, but only ingest holds the Slack integration — the OAuth
bot tokens (encrypted at rest, app/crypto.py) and the notification_channels
an org configured at /settings. This is the HTTP hop the agent needs to
actually deliver to an org's connected Slack workspace, the same pattern
relay_internal.py already established for MCP-server -> ingest telemetry
calls: bearer MCP_INTERNAL_TOKEN, reused here as the general internal
service-to-service secret (see auth.verify_internal_token's docstring).

Delivery is best-effort and always returns 200 with a status field rather
than an error code for "nothing to deliver to" — no connected workspace or
no matching notification_channel is an expected, common state (most orgs
haven't set up Slack), not a caller error.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import crypto, slack_client
from ..auth import verify_internal_token
from ..db import get_session
from ..models.notification_channel import NotificationChannel
from ..models.slack_workspace import SlackWorkspace

logger = logging.getLogger("kubex.ingest.notify_internal")

router = APIRouter(prefix="/internal", tags=["notify-internal"], dependencies=[Depends(verify_internal_token)])


class NotifyRequest(BaseModel):
    org_id: uuid.UUID
    event_type: str
    text: str
    service_id: int | None = None


@router.post("/notify")
async def notify(body: NotifyRequest, session: AsyncSession = Depends(get_session)) -> dict:
    workspace = (
        await session.execute(
            select(SlackWorkspace).where(
                SlackWorkspace.org_id == body.org_id, SlackWorkspace.uninstalled_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if workspace is None:
        return {"status": "skipped", "reason": "no connected Slack workspace"}

    channels = (
        await session.execute(
            select(NotificationChannel).where(
                NotificationChannel.workspace_id == workspace.id,
                NotificationChannel.enabled.is_(True),
            )
        )
    ).scalars().all()
    # A channel with no service_id set is org-wide (every service); one
    # with a service_id only wants that service's events.
    matching = [
        c
        for c in channels
        if body.event_type in c.event_types
        and (c.service_id is None or c.service_id == body.service_id)
    ]
    if not matching:
        return {"status": "skipped", "reason": "no matching notification channel"}

    try:
        token = crypto.decrypt(workspace.bot_token_encrypted)
    except Exception:
        logger.exception("Failed to decrypt Slack bot token for org_id=%s", body.org_id)
        return {"status": "error", "reason": "bot token decrypt failed"}

    delivered: list[str] = []
    for channel in matching:
        try:
            await slack_client.post_message(token, channel.slack_channel_id, body.text)
            channel.last_delivery_at = datetime.now(timezone.utc)
            channel.last_delivery_error = None
            delivered.append(channel.slack_channel_name)
        except Exception as e:  # noqa: BLE001 — one channel's failure must not block the others
            logger.warning("Slack delivery to #%s failed: %s", channel.slack_channel_name, e)
            channel.last_delivery_error = str(e)[:500]

    await session.commit()
    return {"status": "ok" if delivered else "error", "delivered_to": delivered}
