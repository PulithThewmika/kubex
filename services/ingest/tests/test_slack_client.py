"""Slack Web API client helpers (E23-T5 / #828)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from app import slack_client


@pytest.fixture
def call():
    with patch("app.slack_client._call", new=AsyncMock()) as m:
        yield m


@pytest.mark.asyncio
async def test_list_channels_follows_pagination(call):
    call.side_effect = [
        {"ok": True, "channels": [{"id": "C1"}], "response_metadata": {"next_cursor": "x"}},
        {"ok": True, "channels": [{"id": "C2"}], "response_metadata": {"next_cursor": ""}},
    ]
    channels = await slack_client.list_channels("tok")
    assert [c["id"] for c in channels] == ["C1", "C2"]
    assert call.await_count == 2


@pytest.mark.asyncio
async def test_revoke_swallows_slack_error(call):
    call.side_effect = slack_client.SlackError("token_revoked")
    await slack_client.revoke("tok")  # must not raise


@pytest.mark.asyncio
async def test_post_message_serializes_blocks(call):
    call.return_value = {"ok": True}
    await slack_client.post_message("tok", "C1", "hi", [{"type": "section"}])
    kwargs = call.await_args.kwargs
    assert kwargs["channel"] == "C1"
    assert json.loads(kwargs["blocks"]) == [{"type": "section"}]


@pytest.mark.asyncio
async def test_call_retries_once_on_429(monkeypatch):
    import app.slack_client as sc

    calls = []

    class _Resp:
        def __init__(self, status, body):
            self.status_code = status
            self.headers = {"Retry-After": "0"}
            self._body = body

        def raise_for_status(self):
            return None

        def json(self):
            return self._body

    async def _post(path, data=None, headers=None):
        calls.append(path)
        return _Resp(429, {}) if len(calls) == 1 else _Resp(200, {"ok": True})

    client = AsyncMock()
    client.post = _post
    monkeypatch.setattr(sc, "_get_client", lambda: client)
    monkeypatch.setattr(sc.asyncio, "sleep", AsyncMock())
    body = await sc._call("chat.postMessage", token="t", channel="c")
    assert body["ok"] is True
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_call_raises_on_not_ok():
    class _Resp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"ok": False, "error": "channel_not_found"}

    client = AsyncMock()
    client.post = AsyncMock(return_value=_Resp())
    with patch("app.slack_client._get_client", return_value=client):
        with pytest.raises(slack_client.SlackError) as exc:
            await slack_client._call("chat.postMessage", token="t", channel="c")
    assert exc.value.code == "channel_not_found"
