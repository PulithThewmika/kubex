from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from cluster_agent import ingest_client, run
from cluster_agent.backoff import Backoff


@pytest.fixture(autouse=True)
def _reset_shutdown_event():
    run._shutdown_event.clear()
    yield
    run._shutdown_event.clear()


@pytest.mark.asyncio
async def test_run_with_backoff_resets_on_success_and_reports_no_wait():
    backoff = Backoff(initial=1, maximum=60)
    backoff.next_delay()  # simulate a prior failure having advanced it
    already_waited = await run._run_with_backoff("test", backoff, AsyncMock())
    assert already_waited is False
    assert backoff.next_delay() == 1  # back to initial


@pytest.mark.asyncio
async def test_run_with_backoff_sleeps_on_connectivity_error_and_reports_wait():
    backoff = Backoff(initial=1, maximum=60)
    failing = AsyncMock(side_effect=httpx.ConnectError("refused"))
    with patch("cluster_agent.run.asyncio.sleep", AsyncMock()) as mock_sleep:
        already_waited = await run._run_with_backoff("test", backoff, failing)
    mock_sleep.assert_awaited_once_with(1)
    assert already_waited is True


@pytest.mark.asyncio
async def test_run_with_backoff_shuts_down_on_auth_error():
    failing = AsyncMock(side_effect=ingest_client.AuthError("bad token"))
    already_waited = await run._run_with_backoff("test", Backoff(), failing)
    assert already_waited is True
    assert run._shutdown_event.is_set()  # bug found in review: this used to just log and keep retrying forever


@pytest.mark.asyncio
async def test_heartbeat_loop_does_not_stack_interval_sleep_after_backoff():
    # Bug found in review, E22-T3: previously slept backoff_delay AND the
    # full interval on a connectivity failure, instead of backoff alone.
    async def fail_and_shutdown():
        run._shutdown_event.set()  # stop the loop after this one tick
        raise httpx.ConnectError("refused")

    with (
        patch("cluster_agent.run._heartbeat_tick", fail_and_shutdown),
        patch("cluster_agent.run.asyncio.sleep", AsyncMock()) as mock_sleep,
    ):
        await run.heartbeat_loop("cluster-1")
    # Only the backoff sleep should have happened — no extra
    # HEARTBEAT_INTERVAL_SECONDS sleep stacked on top of it before the
    # loop re-checks _shutdown_event and exits.
    mock_sleep.assert_awaited_once_with(1)


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
async def test_bootstrap_retries_on_connectivity_error_then_succeeds():
    identity = {"id": "c1", "name": "my-cluster", "org_id": "o1"}
    call_count = 0

    async def flaky_verify():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise httpx.ConnectError("refused")
        return identity

    with (
        patch("cluster_agent.run.bootstrap_module.verify_identity", flaky_verify),
        patch("cluster_agent.run._discover", AsyncMock()),
        patch("cluster_agent.run.asyncio.sleep", AsyncMock()) as mock_sleep,
    ):
        cluster_id = await run.bootstrap()
    assert cluster_id == "c1"
    mock_sleep.assert_awaited_once()  # retried exactly once before succeeding


@pytest.mark.asyncio
async def test_bootstrap_does_not_retry_auth_error():
    with (
        patch(
            "cluster_agent.run.bootstrap_module.verify_identity",
            AsyncMock(side_effect=ingest_client.AuthError("bad token")),
        ),
        patch("cluster_agent.run._discover", AsyncMock()),
    ):
        with pytest.raises(ingest_client.AuthError):
            await run.bootstrap()


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
