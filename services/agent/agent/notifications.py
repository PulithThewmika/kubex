"""Per-org Slack delivery for deploy health events (E23-T5).

The agent posts directly to each org's Slack workspace right after it
writes an alert row. The in-cluster Alertmanager -> Slack path stays for
platform/infra alerts only.

Bot tokens are stored Fernet-encrypted (INTEGRATION_ENC_KEY, shared with
ingest); this module is the only place the agent decrypts them, and only
in memory at send time.

# ponytail: best-effort, one retry on 429 — the alert row is already
# durable and the UI shows it regardless. A queue + worker only if Slack
# delivery ever needs an SLA.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("kubex.agent.notifications")

INTEGRATION_ENC_KEY = os.environ.get("INTEGRATION_ENC_KEY", "")
SHELL_URL = os.environ.get("SHELL_URL", "http://localhost:5173")
_POST_MESSAGE_URL = "https://slack.com/api/chat.postMessage"

# Slack errors where the channel config is broken beyond a transient blip —
# stop hammering it and surface the reason in the UI.
_FATAL_SLACK_ERRORS = {
    "channel_not_found",
    "not_in_channel",
    "is_archived",
    "token_revoked",
    "account_inactive",
    "invalid_auth",
    "no_permission",
}

_fernet: Fernet | None = None


def _get_fernet() -> Fernet | None:
    global _fernet
    if _fernet is None and INTEGRATION_ENC_KEY:
        _fernet = Fernet(INTEGRATION_ENC_KEY.encode())
    return _fernet


async def _channels_for(
    session: AsyncSession, org_id, service_id: int, event_type: str
) -> list:
    """Enabled channels for this org whose routing scope covers the
    service. Org-scoped — never a cross-tenant read (CLAUDE.md decision 9)."""
    result = await session.execute(
        text(
            """
            SELECT nc.id, nc.slack_channel_id, nc.slack_channel_name,
                   w.bot_token_encrypted
            FROM notification_channels nc
            JOIN slack_workspaces w ON w.id = nc.workspace_id
            WHERE nc.org_id = :org_id
              AND nc.enabled
              AND w.uninstalled_at IS NULL
              AND jsonb_exists(nc.event_types, :event_type)
              AND (nc.service_id IS NULL OR nc.service_id = :service_id)
            """
        ),
        {"org_id": org_id, "service_id": service_id, "event_type": event_type},
    )
    return result.fetchall()


async def _post(token: str, channel_id: str, message: str, blocks: list) -> tuple[bool, str | None]:
    payload = {"channel": channel_id, "text": message, "blocks": blocks}
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        for attempt in (1, 2):
            try:
                resp = await client.post(_POST_MESSAGE_URL, json=payload, headers=headers)
            except httpx.HTTPError:
                return False, "network_error"
            if resp.status_code == 429:
                if attempt == 2:
                    return False, "rate_limited"
                try:
                    delay = int(resp.headers.get("Retry-After", "1"))
                except ValueError:
                    delay = 1
                await asyncio.sleep(min(delay, 30))
                continue
            try:
                body = resp.json()
            except ValueError:
                return False, f"http_{resp.status_code}"
            if body.get("ok"):
                return True, None
            return False, body.get("error") or f"http_{resp.status_code}"
    return False, "rate_limited"


def _deploy_url(deployment_id: int) -> str:
    return urljoin(SHELL_URL, f"/app/deployments/{deployment_id}")


def _evidence_lines(details: dict) -> list[str]:
    penalties = details.get("penalties", {})
    raw = details.get("raw_metrics", {})
    lines: list[str] = []
    if penalties.get("error_rate", 0) > 0:
        lines.append(f"• error rate: {raw.get('error_rate_base')} → {raw.get('error_rate_post')}")
    if penalties.get("latency_p99", 0) > 0:
        lines.append(
            f"• p99 latency: {raw.get('latency_p99_base_ms')}ms → {raw.get('latency_p99_post_ms')}ms"
        )
    if penalties.get("restarts", 0) > 0:
        lines.append(f"• restarts: {raw.get('restarts_base')} → {raw.get('restarts_post')}")
    return lines


def _build_alert_message(
    service_name: str, deployment_id: int, score, verdict: str, details: dict
) -> tuple[str, list]:
    emoji = ":rotating_light:" if verdict == "failed" else ":warning:"
    score_str = f"{score}/100" if score is not None else "n/a"
    summary = f"{emoji} Deploy #{deployment_id} of *{service_name}* scored {score_str} — {verdict}"
    section_text = summary
    evidence = _evidence_lines(details)
    if evidence:
        section_text += "\n" + "\n".join(evidence)
    return summary, [
        {"type": "section", "text": {"type": "mrkdwn", "text": section_text}},
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"<{_deploy_url(deployment_id)}|View in KubeX>"}],
        },
    ]


def _build_recovery_message(service_name: str, deployment_id: int) -> tuple[str, list]:
    summary = f":white_check_mark: Deploy #{deployment_id} of *{service_name}* recovered"
    return summary, [
        {"type": "section", "text": {"type": "mrkdwn", "text": summary}},
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"<{_deploy_url(deployment_id)}|View in KubeX>"}],
        },
    ]


async def _deliver(session: AsyncSession, channels: list, message: str, blocks: list) -> None:
    fernet = _get_fernet()
    if fernet is None:
        return
    now = datetime.now(timezone.utc)
    for ch in channels:
        try:
            token = fernet.decrypt(bytes(ch.bot_token_encrypted)).decode()
        except InvalidToken:
            logger.error(
                "Cannot decrypt Slack token for channel %s — INTEGRATION_ENC_KEY mismatch", ch.id
            )
            continue
        ok, err = await _post(token, ch.slack_channel_id, message, blocks)
        if ok:
            await session.execute(
                text(
                    "UPDATE notification_channels "
                    "SET last_delivery_at = :now, last_delivery_error = NULL WHERE id = :id"
                ),
                {"now": now, "id": ch.id},
            )
        elif err in _FATAL_SLACK_ERRORS:
            await session.execute(
                text(
                    "UPDATE notification_channels "
                    "SET enabled = false, last_delivery_error = :err WHERE id = :id"
                ),
                {"err": err, "id": ch.id},
            )
            logger.warning("Slack channel %s disabled after fatal error: %s", ch.slack_channel_name, err)
        else:
            await session.execute(
                text("UPDATE notification_channels SET last_delivery_error = :err WHERE id = :id"),
                {"err": err, "id": ch.id},
            )
            logger.warning("Slack delivery to %s failed (transient): %s", ch.slack_channel_name, err)
    await session.commit()


async def notify_deploy_alert(
    session: AsyncSession, *, org_id, service_id: int, service_name: str,
    deployment_id: int, score, verdict: str, details: dict,
) -> None:
    """Fire a deploy-degradation notification to the org's Slack channels.
    Never raises — logs and returns on any failure."""
    if not INTEGRATION_ENC_KEY:
        return
    try:
        channels = await _channels_for(session, org_id, service_id, "deploy_health")
        if not channels:
            return
        message, blocks = _build_alert_message(service_name, deployment_id, score, verdict, details)
        await _deliver(session, channels, message, blocks)
    except Exception:
        logger.exception("Slack deploy-alert delivery failed for deployment %d", deployment_id)


async def notify_deploy_recovered(
    session: AsyncSession, *, org_id, service_id: int, service_name: str, deployment_id: int,
) -> None:
    if not INTEGRATION_ENC_KEY:
        return
    try:
        channels = await _channels_for(session, org_id, service_id, "deploy_health")
        if not channels:
            return
        message, blocks = _build_recovery_message(service_name, deployment_id)
        await _deliver(session, channels, message, blocks)
    except Exception:
        logger.exception("Slack recovery delivery failed for deployment %d", deployment_id)
