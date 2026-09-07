"""Slack integration — signature verification, OAuth state, callback,
Events API teardown, crypto, and the owner-only guard (E23-T5 / #828)."""

from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from app.auth import verify_slack_signature
from app.auth_middleware import UserContext, get_current_owner
from tests.conftest import TEST_ORG_ID, TEST_USER_ID

JWT_SECRET = "test-jwt-secret-at-least-32-bytes-long"
SIGNING_SECRET = "test-slack-signing-secret"


# ── crypto ───────────────────────────────────────────────────────────


def test_fernet_round_trip(monkeypatch):
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    monkeypatch.setattr("app.crypto.INTEGRATION_ENC_KEY", key)
    monkeypatch.setattr("app.crypto._fernet", None)
    from app import crypto

    blob = crypto.encrypt("xoxb-super-secret")
    assert blob != b"xoxb-super-secret"
    assert crypto.decrypt(blob) == "xoxb-super-secret"


def test_require_encryption_key_raises_without_key(monkeypatch):
    monkeypatch.setattr("app.crypto.INTEGRATION_ENC_KEY", "")
    monkeypatch.setattr("app.crypto._fernet", None)
    from app import crypto

    with pytest.raises(RuntimeError, match="INTEGRATION_ENC_KEY"):
        crypto.require_encryption_key()


def test_redact_slack_tokens():
    from app.crypto import redact_slack_tokens

    assert redact_slack_tokens("got xoxb-123-abc from slack") == "got xox*** from slack"
    assert "xoxp-" not in redact_slack_tokens("xoxp-9-9-9")
    # app-level, workflow, and rotating token shapes
    assert "xapp-" not in redact_slack_tokens("xapp-1-A-2-bcd")
    assert "xwfp-" not in redact_slack_tokens("xwfp-abc123")
    assert "xoxe.xoxb-" not in redact_slack_tokens("token xoxe.xoxb-1-abc rotates")


# ── signature verification ───────────────────────────────────────────


def _signed_request(body: bytes, *, secret: str = SIGNING_SECRET, ts: int | None = None):
    ts = ts if ts is not None else int(time.time())
    basestring = b"v0:" + str(ts).encode() + b":" + body
    sig = "v0=" + hmac.new(secret.encode(), basestring, hashlib.sha256).hexdigest()
    req = MagicMock()
    req.headers = {"X-Slack-Request-Timestamp": str(ts), "X-Slack-Signature": sig}
    req.body = AsyncMock(return_value=body)
    return req


@pytest.mark.asyncio
async def test_verify_slack_signature_accepts_valid(monkeypatch):
    monkeypatch.setattr("app.auth.SLACK_SIGNING_SECRET", SIGNING_SECRET)
    body = b'{"type":"url_verification"}'
    assert await verify_slack_signature(_signed_request(body)) == body


@pytest.mark.asyncio
async def test_verify_slack_signature_rejects_bad_signature(monkeypatch):
    monkeypatch.setattr("app.auth.SLACK_SIGNING_SECRET", SIGNING_SECRET)
    req = _signed_request(b"{}", secret="wrong-secret")
    with pytest.raises(HTTPException) as exc:
        await verify_slack_signature(req)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_slack_signature_rejects_replay(monkeypatch):
    monkeypatch.setattr("app.auth.SLACK_SIGNING_SECRET", SIGNING_SECRET)
    req = _signed_request(b"{}", ts=int(time.time()) - 600)
    with pytest.raises(HTTPException) as exc:
        await verify_slack_signature(req)
    assert exc.value.status_code == 401
    assert "Stale" in exc.value.detail


@pytest.mark.asyncio
async def test_verify_slack_signature_requires_config(monkeypatch):
    monkeypatch.setattr("app.auth.SLACK_SIGNING_SECRET", "")
    with pytest.raises(HTTPException) as exc:
        await verify_slack_signature(_signed_request(b"{}"))
    assert exc.value.status_code == 503


# ── get_current_owner ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_current_owner_allows_owner():
    session = AsyncMock()
    session.scalar = AsyncMock(return_value="owner")
    with patch("app.auth_middleware.get_current_user", AsyncMock(return_value=UserContext(TEST_USER_ID, TEST_ORG_ID))):
        ctx = await get_current_owner(MagicMock(), session)
    assert ctx.org_id == TEST_ORG_ID


@pytest.mark.asyncio
async def test_get_current_owner_rejects_member():
    session = AsyncMock()
    session.scalar = AsyncMock(return_value="member")
    with patch("app.auth_middleware.get_current_user", AsyncMock(return_value=UserContext(TEST_USER_ID, TEST_ORG_ID))):
        with pytest.raises(HTTPException) as exc:
            await get_current_owner(MagicMock(), session)
    assert exc.value.status_code == 403


# ── OAuth callback ───────────────────────────────────────────────────


@pytest.fixture
def slack_client_env(client: FastAPI, monkeypatch):
    monkeypatch.setattr("app.routers.integrations_slack.SLACK_CLIENT_ID", "cid")
    monkeypatch.setattr("app.routers.integrations_slack.SLACK_CLIENT_SECRET", "csec")
    from cryptography.fernet import Fernet

    monkeypatch.setattr("app.crypto.INTEGRATION_ENC_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr("app.crypto._fernet", None)
    return client


def _state(nonce: str, *, org_id=TEST_ORG_ID, user_id=TEST_USER_ID, expired=False):
    exp = datetime.now(timezone.utc) + timedelta(minutes=-1 if expired else 10)
    return jwt.encode(
        {"nonce": nonce, "org_id": str(org_id), "user_id": str(user_id), "exp": exp},
        JWT_SECRET,
        algorithm="HS256",
    )


@pytest.mark.asyncio
async def test_callback_rejects_tampered_state(slack_client_env):
    async with AsyncClient(transport=ASGITransport(app=slack_client_env), base_url="http://test") as ac:
        resp = await ac.get(
            "/integrations/slack/callback",
            params={"state": "not-a-jwt", "code": "x"},
            cookies={"slack_oauth_nonce": "n"},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_callback_rejects_expired_state(slack_client_env):
    async with AsyncClient(transport=ASGITransport(app=slack_client_env), base_url="http://test") as ac:
        resp = await ac.get(
            "/integrations/slack/callback",
            params={"state": _state("n", expired=True), "code": "x"},
            cookies={"slack_oauth_nonce": "n"},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_callback_rejects_nonce_mismatch(slack_client_env):
    async with AsyncClient(transport=ASGITransport(app=slack_client_env), base_url="http://test") as ac:
        resp = await ac.get(
            "/integrations/slack/callback",
            params={"state": _state("real-nonce"), "code": "x"},
            cookies={"slack_oauth_nonce": "other-nonce"},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_callback_user_denied_redirects(slack_client_env):
    async with AsyncClient(
        transport=ASGITransport(app=slack_client_env), base_url="http://test", follow_redirects=False
    ) as ac:
        resp = await ac.get(
            "/integrations/slack/callback",
            params={"state": _state("n"), "error": "access_denied"},
            cookies={"slack_oauth_nonce": "n"},
        )
    assert resp.status_code == 302
    assert "slack=denied" in resp.headers["location"]


@pytest.mark.asyncio
async def test_callback_happy_path_stores_workspace(slack_client_env, mock_session):
    exchange = AsyncMock(
        return_value={
            "access_token": "xoxb-abc",
            "bot_user_id": "U1",
            "team": {"id": "T1", "name": "Acme"},
        }
    )
    with patch("app.routers.integrations_slack.slack_client.oauth_exchange", exchange):
        async with AsyncClient(
            transport=ASGITransport(app=slack_client_env), base_url="http://test", follow_redirects=False
        ) as ac:
            resp = await ac.get(
                "/integrations/slack/callback",
                params={"state": _state("n"), "code": "code123"},
                cookies={"slack_oauth_nonce": "n"},
            )
    assert resp.status_code == 302
    assert "slack=connected" in resp.headers["location"]
    exchange.assert_awaited_once()
    # the workspace upsert ran
    assert mock_session.execute.await_count >= 1
    mock_session.commit.assert_awaited()


# ── Events API ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_events_url_verification_echoes_challenge(client: FastAPI, monkeypatch):
    monkeypatch.setattr("app.auth.SLACK_SIGNING_SECRET", SIGNING_SECRET)
    body = b'{"type":"url_verification","challenge":"c123"}'
    req = _signed_request(body)
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.post(
            "/webhooks/slack/events",
            content=body,
            headers={
                "X-Slack-Request-Timestamp": req.headers["X-Slack-Request-Timestamp"],
                "X-Slack-Signature": req.headers["X-Slack-Signature"],
            },
        )
    assert resp.status_code == 200
    assert resp.json()["challenge"] == "c123"


@pytest.mark.asyncio
async def test_events_app_uninstalled_tears_down(client: FastAPI, mock_session, monkeypatch):
    monkeypatch.setattr("app.auth.SLACK_SIGNING_SECRET", SIGNING_SECRET)
    from app.models.slack_workspace import SlackWorkspace

    ws = SlackWorkspace(
        id=uuid.uuid4(), org_id=TEST_ORG_ID, slack_team_id="T1",
        bot_token_encrypted=b"x", installed_at=datetime.now(timezone.utc), uninstalled_at=None,
    )
    mock_session.scalars = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[ws])))

    body = b'{"type":"event_callback","team_id":"T1","event":{"type":"app_uninstalled"}}'
    req = _signed_request(body)
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.post(
            "/webhooks/slack/events",
            content=body,
            headers={
                "X-Slack-Request-Timestamp": req.headers["X-Slack-Request-Timestamp"],
                "X-Slack-Signature": req.headers["X-Slack-Signature"],
            },
        )
    assert resp.status_code == 200
    assert ws.uninstalled_at is not None
    mock_session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_events_tokens_revoked_only_for_bot(client: FastAPI, mock_session, monkeypatch):
    """tokens_revoked without our bot in event.tokens.bot is a no-op."""
    monkeypatch.setattr("app.auth.SLACK_SIGNING_SECRET", SIGNING_SECRET)
    mock_session.scalars = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[])))

    body = b'{"type":"event_callback","team_id":"T1","event":{"type":"tokens_revoked","tokens":{"oauth":["U9"]}}}'
    req = _signed_request(body)
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.post(
            "/webhooks/slack/events",
            content=body,
            headers={
                "X-Slack-Request-Timestamp": req.headers["X-Slack-Request-Timestamp"],
                "X-Slack-Signature": req.headers["X-Slack-Signature"],
            },
        )
    assert resp.status_code == 200
    # no bot tokens listed -> no teardown query, no commit
    mock_session.scalars.assert_not_called()


@pytest.mark.asyncio
async def test_teardown_workspace_filters_by_bot_user_id():
    from app.routers.integrations_slack import _teardown_workspace

    session = AsyncMock()
    session.scalars = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    await _teardown_workspace(session, "T1", bot_user_ids=["UBOT1"])
    where = str(session.scalars.await_args.args[0])
    assert "bot_user_id IN" in where
