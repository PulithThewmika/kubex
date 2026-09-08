"""Alertmanager client — fires and resolves deployment degradation alerts.

Posts to Alertmanager v2 API and mirrors alert lifecycle to PostgreSQL.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .config import ALERTMANAGER_URL
from .notify import notify_slack

logger = logging.getLogger("kubex.agent.alerting")

_client: httpx.AsyncClient | None = None


def get_alertmanager_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(base_url=ALERTMANAGER_URL, timeout=10.0)
    return _client


async def close_alertmanager_client() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        _client = None


def _build_alert_payload(
    service_name: str,
    deployment_id: int,
    score: int,
    verdict: str,
    details: dict,
) -> list[dict]:
    """Build Alertmanager v2 API alert payload."""
    severity = "critical" if score < 50 else "warning"

    evidence_parts = []
    penalties = details.get("penalties", {})
    raw = details.get("raw_metrics", {})
    if penalties.get("error_rate", 0) > 0:
        base = raw.get("error_rate_base")
        post = raw.get("error_rate_post")
        evidence_parts.append(
            f"error_rate: {_fmt(base)} → {_fmt(post)} (penalty {penalties['error_rate']:.2f})"
        )
    if penalties.get("latency_p99", 0) > 0:
        base = raw.get("latency_p99_base_ms")
        post = raw.get("latency_p99_post_ms")
        evidence_parts.append(
            f"latency_p99: {_fmt(base)}ms → {_fmt(post)}ms (penalty {penalties['latency_p99']:.2f})"
        )
    if penalties.get("restarts", 0) > 0:
        base = raw.get("restarts_base")
        post = raw.get("restarts_post")
        evidence_parts.append(
            f"restarts: {_fmt(base)} → {_fmt(post)} (penalty {penalties['restarts']:.2f})"
        )

    description = "; ".join(evidence_parts) if evidence_parts else "No specific metric degradation"

    return [{
        "labels": {
            "alertname": "DeployDegradation",
            "service": service_name,
            "deploy_id": str(deployment_id),
            "severity": severity,
        },
        "annotations": {
            "summary": f"Deploy #{deployment_id} of {service_name} scored {score}/100",
            "description": description,
        },
    }]


def _fmt(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.4f}" if value < 1 else f"{value:.1f}"


async def fire_alert(
    session: AsyncSession,
    service_name: str,
    service_id: int,
    deployment_id: int,
    score: int,
    verdict: str,
    details: dict,
    org_id,
) -> int | None:
    """Fire a DeployDegradation alert to Alertmanager and insert alerts row.

    Returns the alert ID from PostgreSQL, or None if DB insert failed.
    """
    severity = "critical" if score < 50 else "warning"
    title = f"Deploy #{deployment_id} of {service_name} scored {score}/100"

    penalties = details.get("penalties", {})
    raw = details.get("raw_metrics", {})
    evidence_parts = []
    if penalties.get("error_rate", 0) > 0:
        evidence_parts.append(f"error_rate: {raw.get('error_rate_base')} → {raw.get('error_rate_post')}")
    if penalties.get("latency_p99", 0) > 0:
        evidence_parts.append(f"latency_p99: {raw.get('latency_p99_base_ms')}ms → {raw.get('latency_p99_post_ms')}ms")
    if penalties.get("restarts", 0) > 0:
        evidence_parts.append(f"restarts: {raw.get('restarts_base')} → {raw.get('restarts_post')}")
    description = "; ".join(evidence_parts) if evidence_parts else "Health degradation detected"

    # Insert alert row into PostgreSQL. org_id is set explicitly (from the
    # deployment this alert belongs to) rather than relying on V014's
    # column DEFAULT — that default silently misattributes every agent-
    # fired alert to the default org regardless of which org the
    # deployment actually belongs to (E20-T2 code review finding).
    result = await session.execute(
        text("""
            INSERT INTO alerts (org_id, deployment_id, service_id, severity, title, description, fired_at)
            VALUES (:org_id, :deployment_id, :service_id, :severity, :title, :description, now())
            RETURNING id
        """),
        {
            "org_id": org_id,
            "deployment_id": deployment_id,
            "service_id": service_id,
            "severity": severity,
            "title": title,
            "description": description,
        },
    )
    alert_id = result.scalar_one()
    logger.info("Alert #%d inserted for deployment %d (severity=%s)", alert_id, deployment_id, severity)

    # Post to Alertmanager
    payload = _build_alert_payload(service_name, deployment_id, score, verdict, details)
    try:
        client = get_alertmanager_client()
        resp = await client.post("/api/v2/alerts", json=payload)
        resp.raise_for_status()
        logger.info("Alert fired to Alertmanager for deployment %d", deployment_id)
    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
        logger.warning("Failed to post alert to Alertmanager (alert still in DB): %s", e)

    await notify_slack(org_id, "deploy_health", f"{title}\n{description}", service_id=service_id)

    return alert_id


async def resolve_alert(
    session: AsyncSession, alert_id: int, service_name: str, deployment_id: int, org_id=None, service_id=None,
) -> None:
    """Send endsAt to Alertmanager and update alerts.resolved_at.

    org_id/service_id are optional only for backward compatibility with any
    caller that predates the Slack notify call below — every real caller
    (reconciliation.py) already has both in hand from its own alert row
    query and should always pass them.
    """
    now = datetime.now(timezone.utc)

    # Fetch severity from the alert row so the resolution label set matches the firing payload
    result = await session.execute(
        text("SELECT severity FROM alerts WHERE id = :alert_id"),
        {"alert_id": alert_id},
    )
    row = result.fetchone()
    severity = row.severity if row else "warning"

    # Update PostgreSQL
    await session.execute(
        text("""
            UPDATE alerts SET resolved_at = :resolved_at
            WHERE id = :alert_id AND resolved_at IS NULL
        """),
        {"resolved_at": now, "alert_id": alert_id},
    )
    logger.info("Alert #%d resolved in DB", alert_id)

    # Send resolution to Alertmanager — labels must match the firing payload exactly
    # so Alertmanager can match the fingerprint and clear the correct alert
    payload = [{
        "labels": {
            "alertname": "DeployDegradation",
            "service": service_name,
            "deploy_id": str(deployment_id),
            "severity": severity,
        },
        "endsAt": now.isoformat(),
    }]
    try:
        client = get_alertmanager_client()
        resp = await client.post("/api/v2/alerts", json=payload)
        resp.raise_for_status()
        logger.info("Alert resolution sent to Alertmanager for deployment %d", deployment_id)
    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
        logger.warning("Failed to send resolution to Alertmanager (DB already updated): %s", e)

    if org_id is not None:
        await notify_slack(
            org_id, "deploy_health", f"✅ Deploy #{deployment_id} of {service_name} recovered", service_id=service_id,
        )
