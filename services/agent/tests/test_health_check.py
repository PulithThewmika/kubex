"""Tests for the HTTP health check fallback (E23-T1-S5)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from agent import health_check as hc


def _mock_service_row(id=1, name="orders", url="https://orders.example.com/health", interval=30):
    row = MagicMock()
    row.id = id
    row.name = name
    row.health_check_url = url
    row.health_check_interval_s = interval
    return row


@pytest.fixture(autouse=True)
def _reset_ring_buffers():
    hc._results.clear()
    yield
    hc._results.clear()


@pytest.mark.asyncio
async def test_ping_records_status_and_response_time():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.is_closed = False
    response = MagicMock()
    response.status_code = 200
    client.get = AsyncMock(return_value=response)

    with patch("agent.health_check._client", client):
        result = await hc.ping("https://orders.example.com/health")

    assert result.status_code == 200
    assert result.response_time_ms >= 0
    assert result.error is None


@pytest.mark.asyncio
async def test_ping_records_error_without_raising():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.is_closed = False
    client.get = AsyncMock(side_effect=httpx.ConnectTimeout("timed out"))

    with patch("agent.health_check._client", client):
        result = await hc.ping("https://orders.example.com/health")

    assert result.status_code is None
    assert result.error is not None


@pytest.mark.asyncio
async def test_run_health_checks_configures_pings_and_stores_result():
    """End-to-end: a configured service gets pinged and the result lands
    in its ring buffer, readable via get_results()."""
    session = AsyncMock()
    result = MagicMock()
    result.fetchall.return_value = [_mock_service_row(id=1, name="orders")]
    session.execute = AsyncMock(return_value=result)

    fake_result = hc.HealthCheckResult(
        checked_at=datetime.now(timezone.utc), status_code=200, response_time_ms=42,
    )
    with patch("agent.health_check.ping", AsyncMock(return_value=fake_result)):
        checked = await hc.run_health_checks(session)

    assert checked == 1
    stored = hc.get_results(1)
    assert len(stored) == 1
    assert stored[0].status_code == 200
    assert stored[0].response_time_ms == 42


@pytest.mark.asyncio
async def test_run_health_checks_skips_service_not_yet_due():
    session = AsyncMock()
    result = MagicMock()
    result.fetchall.return_value = [_mock_service_row(id=2, interval=300)]
    session.execute = AsyncMock(return_value=result)

    hc.record_result(2, hc.HealthCheckResult(
        checked_at=datetime.now(timezone.utc), status_code=200, response_time_ms=10,
    ))

    with patch("agent.health_check.ping", AsyncMock()) as mock_ping:
        checked = await hc.run_health_checks(session)

    assert checked == 0
    mock_ping.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_health_checks_pings_due_services_concurrently() -> None:
    """A slow/unreachable endpoint must not serialize the whole tick —
    max_instances=1 on the scheduler job means an overrun tick is silently
    dropped, not queued (run.py)."""
    import asyncio

    session = AsyncMock()
    result = MagicMock()
    result.fetchall.return_value = [
        _mock_service_row(id=1, name="orders"),
        _mock_service_row(id=2, name="payments"),
    ]
    session.execute = AsyncMock(return_value=result)

    async def slow_ping(url: str) -> hc.HealthCheckResult:
        await asyncio.sleep(0.2)
        return hc.HealthCheckResult(
            checked_at=datetime.now(timezone.utc), status_code=200, response_time_ms=200,
        )

    with patch("agent.health_check.ping", slow_ping):
        started = asyncio.get_event_loop().time()
        checked = await hc.run_health_checks(session)
        elapsed = asyncio.get_event_loop().time() - started

    assert checked == 2
    assert elapsed < 0.35  # would be >=0.4s if pinged sequentially


def test_ring_buffer_caps_at_configured_size():
    for i in range(hc.HEALTH_CHECK_RING_BUFFER_SIZE + 5):
        hc.record_result(3, hc.HealthCheckResult(
            checked_at=datetime.now(timezone.utc) + timedelta(seconds=i),
            status_code=200, response_time_ms=i,
        ))

    stored = hc.get_results(3)
    assert len(stored) == hc.HEALTH_CHECK_RING_BUFFER_SIZE
    assert stored[-1].response_time_ms == hc.HEALTH_CHECK_RING_BUFFER_SIZE + 4
