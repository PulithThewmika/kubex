"""Tests for the internal relay client (#840, app/cluster_relay.py)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app import cluster_relay

ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
CLUSTER_ID = uuid.uuid4()


@pytest.mark.asyncio
async def test_resolve_cluster_for_org_raises_when_none_connected() -> None:
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=None)

    with pytest.raises(cluster_relay.NoClusterError):
        await cluster_relay.resolve_cluster_for_org(session, ORG_ID)


@pytest.mark.asyncio
async def test_resolve_cluster_for_org_returns_cluster_id() -> None:
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=CLUSTER_ID)

    result = await cluster_relay.resolve_cluster_for_org(session, ORG_ID)
    assert result == CLUSTER_ID


@pytest.mark.asyncio
async def test_queue_and_wait_returns_result_once_completed(monkeypatch) -> None:
    query_id = uuid.uuid4()
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=query_id)
    session.commit = AsyncMock()

    completed_row = SimpleNamespace(status="completed", result={"status": "success"})
    execute_result = MagicMock()
    execute_result.first = MagicMock(return_value=completed_row)
    session.execute = AsyncMock(return_value=execute_result)

    monkeypatch.setattr(cluster_relay.asyncio, "sleep", AsyncMock())

    result = await cluster_relay.queue_and_wait(session, CLUSTER_ID, "up", "instant", None, timeout=5)
    assert result == {"status": "success"}
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_queue_and_wait_raises_timeout_when_never_completed() -> None:
    """A vanishingly small timeout means the while-loop's own deadline
    check fails before any real sleep happens, so this hits the
    RelayTimeoutError path near-instantly without mocking time.monotonic
    (which asyncio's own event loop also calls internally, so patching it
    globally is unsafe)."""
    query_id = uuid.uuid4()
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=query_id)
    session.commit = AsyncMock()

    pending_row = SimpleNamespace(status="pending", result=None)
    execute_result = MagicMock()
    execute_result.first = MagicMock(return_value=pending_row)
    session.execute = AsyncMock(return_value=execute_result)

    with pytest.raises(cluster_relay.RelayTimeoutError):
        await cluster_relay.queue_and_wait(session, CLUSTER_ID, "up", "instant", None, timeout=0.001)


@pytest.mark.asyncio
async def test_relay_query_resolves_then_queues(monkeypatch) -> None:
    resolve_mock = AsyncMock(return_value=CLUSTER_ID)
    queue_mock = AsyncMock(return_value={"status": "success"})
    monkeypatch.setattr(cluster_relay, "resolve_cluster_for_org", resolve_mock)
    monkeypatch.setattr(cluster_relay, "queue_and_wait", queue_mock)

    session = object()
    result = await cluster_relay.relay_query(session, ORG_ID, "up", "instant", None)

    assert result == {"status": "success"}
    resolve_mock.assert_awaited_once_with(session, ORG_ID)
    queue_mock.assert_awaited_once_with(session, CLUSTER_ID, "up", "instant", None, None)
