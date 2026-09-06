from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from cluster_agent import ingest_client, run
from cluster_agent.backoff import Backoff


@pytest.mark.asyncio
async def test_run_with_backoff_resets_on_success():
    backoff = Backoff(initial=1, maximum=60)
    backoff.next_delay()  # simulate a prior failure having advanced it
    await run._run_with_backoff("test", backoff, AsyncMock())
    assert backoff.next_delay() == 1  # back to initial


@pytest.mark.asyncio
async def test_run_with_backoff_sleeps_on_connectivity_error():
    backoff = Backoff(initial=1, maximum=60)
    failing = AsyncMock(side_effect=httpx.ConnectError("refused"))
    with patch("cluster_agent.run.asyncio.sleep", AsyncMock()) as mock_sleep:
        await run._run_with_backoff("test", backoff, failing)
    mock_sleep.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_run_with_backoff_swallows_auth_error_without_sleeping():
    failing = AsyncMock(side_effect=ingest_client.AuthError("bad token"))
    with patch("cluster_agent.run.asyncio.sleep", AsyncMock()) as mock_sleep:
        await run._run_with_backoff("test", Backoff(), failing)
    mock_sleep.assert_not_awaited()


@pytest.mark.asyncio
async def test_query_relay_tick_skips_when_prometheus_not_discovered():
    run._state["prometheus_status"] = "not_found"
    with (
        patch("cluster_agent.run.ingest_client.list_queries", AsyncMock(return_value=[{"id": "q1", "promql": "up"}])),
        patch("cluster_agent.run.prometheus.query", AsyncMock()) as mock_query,
    ):
        await run._query_relay_tick("cluster-1")
    mock_query.assert_not_called()


@pytest.mark.asyncio
async def test_query_relay_tick_executes_and_submits_pending_queries():
    run._state["prometheus_status"] = "found"
    run._state["prometheus_namespace"] = "monitoring"
    run._state["prometheus_service"] = "prometheus-operated"
    with (
        patch("cluster_agent.run.ingest_client.list_queries", AsyncMock(return_value=[{"id": "q1", "promql": "up"}])),
        patch("cluster_agent.run.prometheus.query", AsyncMock(return_value={"status": "success"})) as mock_query,
        patch("cluster_agent.run.ingest_client.submit_result", AsyncMock()) as mock_submit,
    ):
        await run._query_relay_tick("cluster-1")
    mock_query.assert_awaited_once()
    mock_submit.assert_awaited_once_with("cluster-1", "q1", {"status": "success"})


@pytest.mark.asyncio
async def test_query_relay_tick_continues_after_one_query_fails():
    run._state["prometheus_status"] = "found"
    run._state["prometheus_namespace"] = "monitoring"
    run._state["prometheus_service"] = "prometheus-operated"
    queries = [{"id": "bad", "promql": "!!!"}, {"id": "q2", "promql": "up"}]
    with (
        patch("cluster_agent.run.ingest_client.list_queries", AsyncMock(return_value=queries)),
        patch("cluster_agent.run.prometheus.query", AsyncMock(side_effect=[Exception("boom"), {"status": "success"}])),
        patch("cluster_agent.run.ingest_client.submit_result", AsyncMock()) as mock_submit,
    ):
        await run._query_relay_tick("cluster-1")
    mock_submit.assert_awaited_once_with("cluster-1", "q2", {"status": "success"})
