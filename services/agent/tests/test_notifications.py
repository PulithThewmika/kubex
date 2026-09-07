"""Per-org Slack delivery from the agent (E23-T5 / #828)."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from cryptography.fernet import Fernet

from agent import notifications

ORG_A = uuid.uuid4()


@pytest.fixture
def enc_key(monkeypatch):
    key = Fernet.generate_key()
    monkeypatch.setattr(notifications, "INTEGRATION_ENC_KEY", key.decode())
    monkeypatch.setattr(notifications, "_fernet", None)
    return Fernet(key)


def _channel_row(enc: Fernet, *, cid=None, name="deploys"):
    row = MagicMock()
    row.id = cid or uuid.uuid4()
    row.slack_channel_id = "C1"
    row.slack_channel_name = name
    row.bot_token_encrypted = enc.encrypt(b"xoxb-token")
    return row


def test_alert_message_has_evidence_and_link():
    details = {
        "penalties": {"error_rate": 0.5, "latency_p99": 0, "restarts": 0},
        "raw_metrics": {"error_rate_base": 0.01, "error_rate_post": 0.06},
    }
    text, blocks = notifications._build_alert_message("orders", 42, 37, "failed", details)
    assert "orders" in text and "37/100" in text
    assert "error rate" in blocks[0]["text"]["text"]
    assert "/app/deployments/42" in blocks[1]["elements"][0]["text"]


@pytest.mark.asyncio
async def test_channels_query_is_org_scoped(enc_key):
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock(fetchall=MagicMock(return_value=[])))
    await notifications._channels_for(session, ORG_A, 7, "deploy_health")
    params = session.execute.await_args.args[1]
    assert params["org_id"] == ORG_A
    assert params["service_id"] == 7
    assert params["event_type"] == "deploy_health"
    sql = str(session.execute.await_args.args[0])
    assert "nc.org_id = :org_id" in sql


@pytest.mark.asyncio
async def test_deliver_success_stamps_delivery(enc_key, monkeypatch):
    session = AsyncMock()
    monkeypatch.setattr(notifications, "_post", AsyncMock(return_value=(True, None)))
    await notifications._deliver(session, [_channel_row(enc_key)], "hi", [])
    sql = str(session.execute.await_args.args[0])
    assert "last_delivery_at = :now" in sql
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_deliver_disables_channel_on_fatal_error(enc_key, monkeypatch):
    session = AsyncMock()
    monkeypatch.setattr(notifications, "_post", AsyncMock(return_value=(False, "channel_not_found")))
    await notifications._deliver(session, [_channel_row(enc_key)], "hi", [])
    sql = str(session.execute.await_args.args[0])
    assert "enabled = false" in sql


@pytest.mark.asyncio
async def test_deliver_records_transient_error_without_disabling(enc_key, monkeypatch):
    session = AsyncMock()
    monkeypatch.setattr(notifications, "_post", AsyncMock(return_value=(False, "rate_limited")))
    await notifications._deliver(session, [_channel_row(enc_key)], "hi", [])
    sql = str(session.execute.await_args.args[0])
    assert "enabled = false" not in sql
    assert "last_delivery_error = :err" in sql


@pytest.mark.asyncio
async def test_post_retries_once_on_429_then_gives_up(monkeypatch):
    resp = MagicMock(status_code=429, headers={"Retry-After": "0"})
    post = AsyncMock(return_value=resp)

    @asynccontextmanager
    async def fake_client(*a, **kw):
        c = MagicMock()
        c.post = post
        yield c

    monkeypatch.setattr(notifications.httpx, "AsyncClient", fake_client)
    monkeypatch.setattr(notifications.asyncio, "sleep", AsyncMock())
    ok, err = await notifications._post("tok", "C1", "hi", [])
    assert ok is False
    assert err == "rate_limited"
    assert post.await_count == 2


@pytest.mark.asyncio
async def test_notify_is_noop_without_key(monkeypatch):
    monkeypatch.setattr(notifications, "INTEGRATION_ENC_KEY", "")
    session = AsyncMock()
    await notifications.notify_deploy_alert(
        session, org_id=ORG_A, service_id=1, service_name="x",
        deployment_id=1, score=10, verdict="failed", details={},
    )
    session.execute.assert_not_called()
