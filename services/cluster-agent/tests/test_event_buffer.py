from __future__ import annotations

from unittest.mock import AsyncMock, patch

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
