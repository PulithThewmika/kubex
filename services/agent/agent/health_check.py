"""HTTP health check fallback (E23-T1) — services without Prometheus.

Pings each service's configured health_check_url and records its response
time and status code. E23-T2 (adaptive health scoring, out of scope here)
will later consume these as an alternative metrics source.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

import httpx
from sqlalchemy import Row, text
from sqlalchemy.ext.asyncio import AsyncSession

from .config import (
    HEALTH_CHECK_MAX_CONCURRENCY,
    HEALTH_CHECK_RING_BUFFER_SIZE,
    BASELINE_WINDOW_SECONDS,
    OBSERVATION_WINDOW_SECONDS,
)

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


async def _find_configured_services(session: AsyncSession) -> Sequence[Row]:
    """All services with a health check URL configured."""
    result = await session.execute(
        text("""
            SELECT id, name, health_check_url, health_check_interval_s
            FROM services
            WHERE health_check_url IS NOT NULL
        """)
    )
    return result.fetchall()


# service_id -> ring buffer of its last N results (E23-T1-S4). In-memory
# only — resets on agent restart, and deliberately not persisted since
# these are short-lived samples feeding a live score, not an audit trail.
_results: dict[int, deque[HealthCheckResult]] = {}


def _buffer_capacity(interval_s: int) -> int:
    """Ring buffer must span baseline+observation windows (E23-T2's adaptive
    scoring reads back that far), not just HEALTH_CHECK_RING_BUFFER_SIZE's
    flat default — otherwise the baseline window is silently empty for any
    interval short enough that the default cap rolls off in under ~45 min.
    """
    window_span_s = BASELINE_WINDOW_SECONDS + OBSERVATION_WINDOW_SECONDS
    needed = -(-window_span_s // interval_s) + 5  # ceil division + safety margin
    return max(HEALTH_CHECK_RING_BUFFER_SIZE, needed)


def record_result(service_id: int, result: HealthCheckResult, interval_s: int = 30) -> None:
    capacity = _buffer_capacity(interval_s)
    buffer = _results.get(service_id)
    if buffer is None or buffer.maxlen != capacity:
        # Reconfiguring a service's health_check_interval_s changes its
        # required capacity — resize in place (keeping existing samples)
        # rather than pinning to whatever interval was first observed.
        buffer = deque(buffer or (), maxlen=capacity)
        _results[service_id] = buffer
    buffer.append(result)


def get_results(service_id: int) -> list[HealthCheckResult]:
    """Most recent health check results for a service, oldest first."""
    return list(_results.get(service_id, ()))


def _is_due(service_id: int, interval_s: int, now: datetime) -> bool:
    buffer = _results.get(service_id)
    if not buffer:
        return True
    return (now - buffer[-1].checked_at).total_seconds() >= interval_s


_ping_semaphore = asyncio.Semaphore(HEALTH_CHECK_MAX_CONCURRENCY)


async def _ping_bounded(url: str) -> HealthCheckResult:
    async with _ping_semaphore:
        return await ping(url)


async def run_health_checks(session: AsyncSession) -> int:
    """Ping every service whose health check interval has elapsed and
    record the result in its ring buffer.

    Pings run concurrently (bounded by HEALTH_CHECK_MAX_CONCURRENCY) —
    sequential awaits would let a handful of slow/unreachable endpoints
    push a single tick past HEALTH_CHECK_TICK_SECONDS, and the job is
    registered with max_instances=1 (run.py), so an overrun tick is
    silently dropped rather than queued.

    Returns the number of services checked this tick.
    """
    services = await _find_configured_services(session)
    now = datetime.now(timezone.utc)
    due = [row for row in services if _is_due(row.id, row.health_check_interval_s, now)]
    results = await asyncio.gather(*(_ping_bounded(row.health_check_url) for row in due))
    for row, result in zip(due, results):
        record_result(row.id, result, row.health_check_interval_s)
        logger.info(
            "Health check %s: status=%s response_time_ms=%d%s",
            row.name, result.status_code, result.response_time_ms,
            f" error={result.error}" if result.error else "",
        )
    return len(due)
