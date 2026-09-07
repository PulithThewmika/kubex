"""Slack Web API client (E23-T5) — ingest side.

Only the calls the OAuth flow and channel-management endpoints need. The
detection agent has its own minimal poster (it runs as a separate
service and can't import this package).
"""

from __future__ import annotations

import asyncio
import json

import httpx

SLACK_API = "https://slack.com/api"

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(base_url=SLACK_API, timeout=10.0)
    return _client


async def close_client() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        _client = None


class SlackError(Exception):
    """A Slack response with ``ok: false``. ``code`` is Slack's ``error``."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(f"Slack API error: {code}")


_RETRY_AFTER_CAP_SECONDS = 30


async def _call(method: str, token: str | None = None, **params: str) -> dict:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    for attempt in (1, 2):
        resp = await _get_client().post(f"/{method}", data=params, headers=headers)
        if resp.status_code == 429 and attempt == 1:
            try:
                delay = int(resp.headers.get("Retry-After", "1"))
            except ValueError:
                delay = 1
            await asyncio.sleep(min(delay, _RETRY_AFTER_CAP_SECONDS))
            continue
        resp.raise_for_status()
        body = resp.json()
        if not body.get("ok"):
            raise SlackError(body.get("error", "unknown"))
        return body
    raise SlackError("ratelimited")


async def oauth_exchange(
    client_id: str, client_secret: str, code: str, redirect_uri: str
) -> dict:
    return await _call(
        "oauth.v2.access",
        client_id=client_id,
        client_secret=client_secret,
        code=code,
        redirect_uri=redirect_uri,
    )


async def revoke(token: str) -> None:
    """Best-effort — a token Slack already considers invalid is fine."""
    try:
        await _call("auth.revoke", token=token)
    except SlackError:
        pass


async def list_channels(token: str) -> list[dict]:
    channels: list[dict] = []
    cursor: str | None = None
    # ponytail: cap at 10 pages (~2000 channels). Page from the picker UI
    # if a workspace ever has more.
    for _ in range(10):
        extra = {"cursor": cursor} if cursor else {}
        body = await _call(
            "conversations.list",
            token=token,
            types="public_channel,private_channel",
            exclude_archived="true",
            limit="200",
            **extra,
        )
        channels.extend(body.get("channels", []))
        cursor = body.get("response_metadata", {}).get("next_cursor") or None
        if not cursor:
            break
    return channels


async def join_channel(token: str, channel_id: str) -> None:
    await _call("conversations.join", token=token, channel=channel_id)


async def post_message(
    token: str, channel: str, text: str, blocks: list | None = None
) -> dict:
    params: dict[str, str] = {"channel": channel, "text": text}
    if blocks is not None:
        params["blocks"] = json.dumps(blocks)
    return await _call("chat.postMessage", token=token, **params)
