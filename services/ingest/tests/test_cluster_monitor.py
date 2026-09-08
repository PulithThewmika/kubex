"""Tests for the cluster disconnect sweep (E22-T1-S11)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.cluster_monitor import DISCONNECT_THRESHOLD, mark_stale_clusters_disconnected


@pytest.mark.asyncio
async def test_marks_connected_cluster_disconnected_past_threshold() -> None:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock(rowcount=1))
    session.commit = AsyncMock()

    count = await mark_stale_clusters_disconnected(session)

    assert count == 1
    session.commit.assert_awaited_once()
    stmt = session.execute.await_args.args[0]
    assert "UPDATE clusters" in str(stmt)
    assert stmt.compile().params["status"] == "disconnected"


@pytest.mark.asyncio
async def test_no_op_when_nothing_stale() -> None:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock(rowcount=0))
    session.commit = AsyncMock()

    count = await mark_stale_clusters_disconnected(session)

    assert count == 0


def test_disconnect_threshold_is_three_minutes() -> None:
    assert DISCONNECT_THRESHOLD == timedelta(minutes=3)


@pytest.mark.asyncio
async def test_reaps_stale_cluster_queries() -> None:
    from app.cluster_monitor import reap_stale_cluster_queries

    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock(rowcount=3))
    session.commit = AsyncMock()

    count = await reap_stale_cluster_queries(session)

    assert count == 3
    session.commit.assert_awaited_once()
    stmt = session.execute.await_args.args[0]
    assert "DELETE FROM cluster_queries" in str(stmt)
