from __future__ import annotations

import logging
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from cluster_agent import event_buffer, run


def test_buffer_push_drain_and_capacity() -> None:
    event_buffer.drain()  # start clean
    for i in range(105):
        event_buffer.push({"i": i})
    assert event_buffer.size() == 100  # capped, oldest 5 dropped
    drained = event_buffer.drain()
    assert len(drained) == 100
    assert drained[0]["i"] == 5  # oldest surviving entry
    assert event_buffer.size() == 0


@pytest.mark.asyncio
async def test_discover_buffers_status_transition() -> None:
    event_buffer.drain()
    run._state["argocd_status"] = "found"
    with patch(
        "cluster_agent.run.argocd.discover",
        AsyncMock(return_value={"status": "not_found", "version": None, "namespace": None}),
    ), patch("cluster_agent.run.prometheus.discover", AsyncMock(return_value={"status": "found", "namespace": "monitoring", "service_name": "prom"})):
        await run._discover()
    assert event_buffer.size() == 1
    event = event_buffer.drain()[0]
    assert event["from_status"] == "found"
    assert event["to_status"] == "not_found"


@pytest.mark.asyncio
async def test_heartbeat_tick_flushes_buffer_on_success() -> None:
    event_buffer.drain()
    event_buffer.push({"from_status": "found", "to_status": "not_found"})
    with patch("cluster_agent.run.ingest_client.heartbeat", AsyncMock(return_value={})):
        await run._heartbeat_tick()
    assert event_buffer.size() == 0


@pytest.mark.asyncio
async def test_heartbeat_tick_retains_buffer_on_failure_then_logs_and_drains_on_success(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A regression that dropped the buffer without reporting it would pass
    a check for size()==0 alone — assert the outage transition actually got
    logged before it's cleared."""
    event_buffer.drain()
    event = {"from_status": "found", "to_status": "not_found"}
    event_buffer.push(event)

    with patch("cluster_agent.run.ingest_client.heartbeat", AsyncMock(side_effect=httpx.ConnectError("refused"))):
        with pytest.raises(httpx.ConnectError):
            await run._heartbeat_tick()
    assert event_buffer.size() == 1  # retained — heartbeat never reached ingest

    with caplog.at_level(logging.WARNING, logger="kubex.cluster_agent"):
        with patch("cluster_agent.run.ingest_client.heartbeat", AsyncMock(return_value={})):
            await run._heartbeat_tick()
    assert event_buffer.size() == 0
    assert any(str(event) in record.getMessage() for record in caplog.records)
