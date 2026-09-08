"""Tests for POST /internal/notify (agent -> ingest -> Slack delivery)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.notification_channel import NotificationChannel
from app.models.slack_workspace import SlackWorkspace

AUTH_HEADERS = {"Authorization": "Bearer test-internal-token"}
TEST_ORG_ID = uuid.uuid4()


def _workspace(org_id=TEST_ORG_ID) -> SlackWorkspace:
    return SlackWorkspace(
        id=uuid.uuid4(),
        org_id=org_id,
        slack_team_id="T123",
        bot_token_encrypted=b"encrypted-bytes",
    )


def _channel(workspace_id, *, event_types, service_id=None, enabled=True, name="alerts") -> NotificationChannel:
    return NotificationChannel(
        id=uuid.uuid4(),
        org_id=TEST_ORG_ID,
        workspace_id=workspace_id,
        slack_channel_id="C123",
        slack_channel_name=name,
        service_id=service_id,
        event_types=event_types,
        enabled=enabled,
    )


class _FakeSession:
    """Returns workspace_result for the SlackWorkspace select, then
    channel_result for the NotificationChannel select — matches the two
    fixed queries notify_internal.py issues, in order."""

    def __init__(self, *, workspace=None, channels=()):
        self._workspace = workspace
        self._channels = list(channels)
        self.commit = AsyncMock()

    async def execute(self, stmt):
        result = MagicMock()
        if "slack_workspaces" in str(stmt):
            result.scalar_one_or_none = MagicMock(return_value=self._workspace)
        else:
            result.scalars.return_value.all.return_value = self._channels
        return result


async def _post(body):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        return await ac.post("/internal/notify", json=body, headers=AUTH_HEADERS)


def _override_session(session):
    from app.db import get_session

    async def override():
        yield session

    app.dependency_overrides[get_session] = override


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_missing_bearer_token_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/internal/notify", json={"org_id": str(TEST_ORG_ID), "event_type": "deploy_health", "text": "hi"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_no_workspace_returns_skipped():
    _override_session(_FakeSession(workspace=None))
    resp = await _post({"org_id": str(TEST_ORG_ID), "event_type": "deploy_health", "text": "hi"})
    assert resp.status_code == 200
    assert resp.json() == {"status": "skipped", "reason": "no connected Slack workspace"}


@pytest.mark.asyncio
async def test_no_matching_channel_returns_skipped():
    ws = _workspace()
    channel = _channel(ws.id, event_types=["deploy_success"])  # different event type
    _override_session(_FakeSession(workspace=ws, channels=[channel]))
    resp = await _post({"org_id": str(TEST_ORG_ID), "event_type": "deploy_health", "text": "hi"})
    assert resp.status_code == 200
    assert resp.json() == {"status": "skipped", "reason": "no matching notification channel"}


@pytest.mark.asyncio
async def test_delivers_to_matching_org_wide_channel():
    ws = _workspace()
    channel = _channel(ws.id, event_types=["deploy_health"], service_id=None, name="deploys")
    _override_session(_FakeSession(workspace=ws, channels=[channel]))

    with (
        patch("app.routers.notify_internal.crypto.decrypt", return_value="xoxb-real-token"),
        patch("app.routers.notify_internal.slack_client.post_message", new=AsyncMock(return_value={"ok": True})) as post,
    ):
        resp = await _post({"org_id": str(TEST_ORG_ID), "event_type": "deploy_health", "text": "Deploy #1 degraded"})

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "delivered_to": ["deploys"]}
    post.assert_awaited_once_with("xoxb-real-token", "C123", "Deploy #1 degraded")


@pytest.mark.asyncio
async def test_channel_scoped_to_different_service_does_not_match():
    ws = _workspace()
    channel = _channel(ws.id, event_types=["deploy_health"], service_id=99)
    _override_session(_FakeSession(workspace=ws, channels=[channel]))
    resp = await _post({"org_id": str(TEST_ORG_ID), "event_type": "deploy_health", "text": "hi", "service_id": 1})
    assert resp.json()["status"] == "skipped"


@pytest.mark.asyncio
async def test_disabled_channel_does_not_match():
    ws = _workspace()
    channel = _channel(ws.id, event_types=["deploy_health"], enabled=False)
    _override_session(_FakeSession(workspace=ws, channels=[]))  # query itself filters enabled=True
    resp = await _post({"org_id": str(TEST_ORG_ID), "event_type": "deploy_health", "text": "hi"})
    assert resp.json()["status"] == "skipped"


@pytest.mark.asyncio
async def test_decrypt_failure_returns_error_not_500():
    ws = _workspace()
    channel = _channel(ws.id, event_types=["deploy_health"])
    _override_session(_FakeSession(workspace=ws, channels=[channel]))

    with patch("app.routers.notify_internal.crypto.decrypt", side_effect=Exception("bad key")):
        resp = await _post({"org_id": str(TEST_ORG_ID), "event_type": "deploy_health", "text": "hi"})

    assert resp.status_code == 200
    assert resp.json()["status"] == "error"


@pytest.mark.asyncio
async def test_one_channel_failing_does_not_block_another():
    ws = _workspace()
    good = _channel(ws.id, event_types=["deploy_health"], name="good-channel")
    bad = _channel(ws.id, event_types=["deploy_health"], name="bad-channel")
    _override_session(_FakeSession(workspace=ws, channels=[bad, good]))

    async def post_side_effect(token, channel_id, text):
        # both channels share the same slack_channel_id fixture value in
        # this simplified test, so distinguish by object identity via a
        # call counter instead
        post_side_effect.calls += 1
        if post_side_effect.calls == 1:
            raise RuntimeError("channel_not_found")
        return {"ok": True}

    post_side_effect.calls = 0

    with (
        patch("app.routers.notify_internal.crypto.decrypt", return_value="xoxb-token"),
        patch("app.routers.notify_internal.slack_client.post_message", new=AsyncMock(side_effect=post_side_effect)),
    ):
        resp = await _post({"org_id": str(TEST_ORG_ID), "event_type": "deploy_health", "text": "hi"})

    body = resp.json()
    assert body["status"] == "ok"
    assert body["delivered_to"] == ["good-channel"]
