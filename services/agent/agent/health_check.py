"""HTTP health check fallback (E23-T1) — services without Prometheus.

Pings each service's configured health_check_url and records its response
time and status code. E23-T2 (adaptive health scoring, out of scope here)
will later consume these as an alternative metrics source.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from sqlalchemy import text

logger = logging.getLogger("kubex.agent.health_check")

_client: httpx.AsyncClient | None = None


def get_health_check_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=10.0)
    return _client


async def close_health_check_client() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        _client = None


@dataclass
class HealthCheckResult:
    checked_at: datetime
    status_code: int | None
    response_time_ms: int
    error: str | None = None


async def ping(url: str) -> HealthCheckResult:
    """GET the given URL and record its response time and status code.

    A connection failure/timeout is recorded as a result with
    status_code=None rather than raised — a dead health-check endpoint is
    itself a signal, not something that should crash the agent loop.
    """
    client = get_health_check_client()
    started = time.monotonic()
    try:
        response = await client.get(url)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return HealthCheckResult(
            checked_at=datetime.now(timezone.utc),
            status_code=response.status_code,
            response_time_ms=elapsed_ms,
        )
    except httpx.HTTPError as exc:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return HealthCheckResult(
            checked_at=datetime.now(timezone.utc),
            status_code=None,
            response_time_ms=elapsed_ms,
            error=str(exc),
        )


async def _find_configured_services(session):
    """All services with a health check URL configured."""
    result = await session.execute(
        text("""
            SELECT id, name, health_check_url, health_check_interval_s
            FROM services
            WHERE health_check_url IS NOT NULL
        """)
    )
    return result.fetchall()


async def run_health_checks(session) -> int:
    """Ping every configured service's health check URL.

    Returns the number of services checked this tick.
    """
    services = await _find_configured_services(session)
    for row in services:
        result = await ping(row.health_check_url)
        logger.info(
            "Health check %s: status=%s response_time_ms=%d%s",
            row.name, result.status_code, result.response_time_ms,
            f" error={result.error}" if result.error else "",
        )
    return len(services)
