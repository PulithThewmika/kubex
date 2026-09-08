"""Multi-tenant Slack integration (E23-T5).

One distribution-enabled KubeX Slack app; each org installs it into its
own workspace via OAuth v2 (mirrors the GitHub App: one app, N per-org
installs). The resulting bot token is stored Fernet-encrypted, bound to
``org_id``.

Trust model for the callback: Slack redirects the browser back with a
top-level GET, on which the ``session`` cookie (SameSite=Strict) is *not*
sent — so the callback cannot use ``get_current_user``. Instead the
install endpoint (which *is* owner-guarded) mints a short-lived signed
``state`` JWT carrying ``org_id``/``user_id``, and mirrors its nonce into
a SameSite=Lax cookie. The callback trusts the org/user in that state.
Same login-CSRF defense as the GitHub OAuth flow (routers/auth.py).
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urljoin

import httpx
import jwt
from cryptography.fernet import InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .. import slack_client
from ..auth import JWT_SECRET, SHELL_URL, verify_slack_signature
from ..auth_middleware import UserContext, get_current_owner, get_current_user
from ..crypto import decrypt, encrypt, require_encryption_key
from ..db import get_session
from ..models.notification_channel import NotificationChannel
from ..models.service import Service
from ..models.slack_workspace import SlackWorkspace
from ..schemas.slack import (
    AddChannelRequest,
    SlackChannelResponse,
    SlackConnectionResponse,
    SlackPickerChannel,
)

logger = logging.getLogger("kubex.integrations.slack")

SLACK_CLIENT_ID = os.environ.get("SLACK_CLIENT_ID", "")
SLACK_CLIENT_SECRET = os.environ.get("SLACK_CLIENT_SECRET", "")
SLACK_AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"
SLACK_BOT_SCOPES = "chat:write,chat:write.public,channels:read,groups:read"

STATE_TTL_MINUTES = 10
NONCE_COOKIE = "slack_oauth_nonce"
CALLBACK_ROUTE = "slack_oauth_callback"
_CALLBACK_PATH = "/integrations/slack/callback"
_SETTINGS_PATH = "/app/settings"


def _callback_url() -> str:
    """redirect_uri from SHELL_URL, not request.url_for() — behind Vercel's
    rewrite the request Host is the API destination, not the browser origin,
    so url_for() would send Slack's redirect to the wrong host (see auth.py)."""
    return urljoin(SHELL_URL, _CALLBACK_PATH)


router = APIRouter(prefix="/integrations/slack", tags=["integrations"])
api_router = APIRouter(prefix="/api/settings/slack", tags=["integrations"])
events_router = APIRouter(prefix="/webhooks/slack", tags=["webhooks"])


def slack_enabled() -> bool:
    return bool(SLACK_CLIENT_ID and SLACK_CLIENT_SECRET)


def validate_slack_config() -> None:
    """Startup check — call from the app lifespan. If the Slack app is
    configured at all, its signing secret and the integration encryption
    key must both be present and valid."""
    if not slack_enabled():
        return
    if not os.environ.get("SLACK_SIGNING_SECRET"):
        raise RuntimeError(
            "SLACK_SIGNING_SECRET must be set when SLACK_CLIENT_ID is configured "
            "(it verifies inbound Slack Events API requests)."
        )
    require_encryption_key()


def _settings_redirect(status: str) -> RedirectResponse:
    url = urljoin(SHELL_URL, f"{_SETTINGS_PATH}?{urlencode({'tab': 'connections', 'slack': status})}")
    return RedirectResponse(url=url, status_code=302, headers={"Cache-Control": "no-store"})


def _require_enabled() -> None:
    if not slack_enabled():
        raise HTTPException(status_code=503, detail="Slack integration is not configured on this server")


@router.get("/install")
async def slack_install(
    request: Request,
    user: UserContext = Depends(get_current_owner),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    _require_enabled()
    # One workspace per org. Re-authing the *same* workspace goes through the
    # callback's upsert fine; connecting a *different* one must disconnect
    # first, otherwise _active_workspace / disconnect become ambiguous.
    if await _active_workspace(session, user.org_id) is not None:
        raise HTTPException(
            status_code=409,
            detail="A Slack workspace is already connected. Disconnect it first.",
        )
    nonce = secrets.token_urlsafe(16)
    state = jwt.encode(
        {
            "nonce": nonce,
            "org_id": str(user.org_id),
            "user_id": str(user.user_id),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=STATE_TTL_MINUTES),
        },
        JWT_SECRET,
        algorithm="HS256",
    )
    params = urlencode(
        {
            "client_id": SLACK_CLIENT_ID,
            "scope": SLACK_BOT_SCOPES,
            "redirect_uri": _callback_url(),
            "state": state,
        }
    )
    response = RedirectResponse(
        url=f"{SLACK_AUTHORIZE_URL}?{params}",
        headers={"Cache-Control": "no-store"},
    )
    response.set_cookie(
        key=NONCE_COOKIE,
        value=nonce,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=STATE_TTL_MINUTES * 60,
        path="/integrations/slack",
    )
    return response


@router.get("/callback", name=CALLBACK_ROUTE)
async def slack_oauth_callback(
    request: Request,
    state: str = Query(...),
    code: str | None = Query(default=None),
    error: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    _require_enabled()

    nonce_cookie = request.cookies.get(NONCE_COOKIE)
    try:
        claims = jwt.decode(state, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired OAuth state") from None
    if not nonce_cookie or not secrets.compare_digest(
        nonce_cookie.encode(), claims.get("nonce", "").encode()
    ):
        raise HTTPException(status_code=401, detail="Missing or mismatched OAuth nonce")

    if error or not code:
        logger.info("Slack OAuth cancelled or failed: error=%s", error)
        resp = _settings_redirect("denied")
        resp.delete_cookie(key=NONCE_COOKIE, path="/integrations/slack")
        return resp

    try:
        org_id = uuid.UUID(claims["org_id"])
        connected_by = uuid.UUID(claims["user_id"])
    except (KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Malformed OAuth state") from None

    try:
        data = await slack_client.oauth_exchange(
            SLACK_CLIENT_ID,
            SLACK_CLIENT_SECRET,
            code,
            _callback_url(),
        )
    except (httpx.HTTPError, slack_client.SlackError) as exc:
        logger.warning("Slack oauth.v2.access failed: %s", exc)
        raise HTTPException(status_code=502, detail="Slack token exchange failed") from None

    access_token = data.get("access_token")
    team = data.get("team") or {}
    team_id = team.get("id")
    if not access_token or not team_id:
        logger.warning("Slack oauth.v2.access response missing access_token/team")
        raise HTTPException(status_code=502, detail="Slack token exchange returned an unexpected response")

    row = {
        "slack_team_name": team.get("name"),
        "bot_token_encrypted": encrypt(access_token),
        "bot_user_id": data.get("bot_user_id"),
        "connected_by": connected_by,
        "installed_at": datetime.now(timezone.utc),
        "uninstalled_at": None,
    }
    stmt = (
        pg_insert(SlackWorkspace)
        .values(org_id=org_id, slack_team_id=team_id, **row)
        .on_conflict_do_update(index_elements=["org_id", "slack_team_id"], set_=row)
        .returning(SlackWorkspace.id)
    )
    try:
        workspace_id = (await session.execute(stmt)).scalar_one()
    except IntegrityError:
        # uq_slack_workspaces_active_per_org — this org already connected a
        # *different* workspace between slack_install's check and now.
        await session.rollback()
        logger.info("Slack connect rejected for org_id=%s — already has an active workspace", org_id)
        resp = _settings_redirect("exists")
        resp.delete_cookie(key=NONCE_COOKIE, path="/integrations/slack")
        return resp
    # A reconnect revives channels a prior teardown disabled — but only
    # those, not ones disabled by a real per-channel failure.
    await session.execute(
        update(NotificationChannel)
        .where(
            NotificationChannel.workspace_id == workspace_id,
            NotificationChannel.enabled.is_(False),
            NotificationChannel.last_delivery_error == "workspace disconnected",
        )
        .values(enabled=True, last_delivery_error=None)
    )
    await session.commit()
    logger.info("Slack workspace connected: org_id=%s team_id=%s", org_id, team_id)

    resp = _settings_redirect("connected")
    resp.delete_cookie(key=NONCE_COOKIE, path="/integrations/slack")
    return resp


async def _active_workspace(session: AsyncSession, org_id: uuid.UUID) -> SlackWorkspace | None:
    # slack_install blocks a second active connection, but order + limit here
    # keeps the pick deterministic even if one slips through (e.g. a race).
    return await session.scalar(
        select(SlackWorkspace)
        .where(
            SlackWorkspace.org_id == org_id,
            SlackWorkspace.uninstalled_at.is_(None),
        )
        .order_by(SlackWorkspace.installed_at.desc())
        .limit(1)
    )


def _channel_response(row: NotificationChannel) -> SlackChannelResponse:
    return SlackChannelResponse(
        id=str(row.id),
        slack_channel_id=row.slack_channel_id,
        slack_channel_name=row.slack_channel_name,
        service_id=row.service_id,
        event_types=list(row.event_types),
        enabled=row.enabled,
        last_delivery_at=row.last_delivery_at,
        last_delivery_error=row.last_delivery_error,
    )


@api_router.get("", response_model=SlackConnectionResponse)
async def get_slack_connection(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SlackConnectionResponse:
    workspace = await _active_workspace(session, user.org_id)
    if workspace is None:
        return SlackConnectionResponse(connected=False)
    channels = (
        await session.scalars(
            select(NotificationChannel)
            .where(NotificationChannel.workspace_id == workspace.id)
            .order_by(NotificationChannel.created_at)
        )
    ).all()
    return SlackConnectionResponse(
        connected=True,
        workspace_id=str(workspace.id),
        team_name=workspace.slack_team_name,
        channels=[_channel_response(c) for c in channels],
    )


@api_router.delete("", status_code=204, response_model=None)
async def disconnect_slack(
    user: UserContext = Depends(get_current_owner),
    session: AsyncSession = Depends(get_session),
) -> None:
    workspace = await _active_workspace(session, user.org_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="No Slack workspace connected")
    try:
        await slack_client.revoke(_bot_token(workspace))
    except Exception:  # noqa: BLE001 — revoke is best-effort, disconnect proceeds
        logger.warning("Slack auth.revoke failed during disconnect for org_id=%s", user.org_id)
    await session.execute(
        delete(NotificationChannel).where(NotificationChannel.workspace_id == workspace.id)
    )
    await session.execute(delete(SlackWorkspace).where(SlackWorkspace.id == workspace.id))
    await session.commit()
    logger.info("Slack workspace disconnected: org_id=%s", user.org_id)


async def _owned_active_workspace(session: AsyncSession, org_id: uuid.UUID) -> SlackWorkspace:
    workspace = await _active_workspace(session, org_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="No Slack workspace connected")
    return workspace


def _bot_token(workspace: SlackWorkspace) -> str:
    """Decrypt the stored bot token, or 502 if the key can't open it
    (e.g. INTEGRATION_ENC_KEY was rotated) — never surfaces the cause."""
    try:
        return decrypt(workspace.bot_token_encrypted)
    except InvalidToken:
        logger.error("Cannot decrypt Slack bot token for org_id=%s", workspace.org_id)
        raise HTTPException(status_code=502, detail="Stored Slack credentials are unreadable") from None


@api_router.get("/channels/available", response_model=list[SlackPickerChannel])
async def list_available_channels(
    user: UserContext = Depends(get_current_owner),
    session: AsyncSession = Depends(get_session),
) -> list[SlackPickerChannel]:
    """Channels the bot can see, for the add-channel picker. Private
    channels only appear once the bot has been /invite'd."""
    workspace = await _owned_active_workspace(session, user.org_id)
    try:
        channels = await slack_client.list_channels(_bot_token(workspace))
    except (httpx.HTTPError, slack_client.SlackError) as exc:
        logger.warning("Slack conversations.list failed for org_id=%s: %s", user.org_id, exc)
        raise HTTPException(status_code=502, detail="Could not list Slack channels") from None
    return [
        SlackPickerChannel(
            slack_channel_id=c["id"],
            name=c.get("name", c["id"]),
            is_private=bool(c.get("is_private")),
            is_member=bool(c.get("is_member")),
        )
        for c in channels
    ]


@api_router.post("/channels", response_model=SlackChannelResponse, status_code=201)
async def add_channel(
    body: AddChannelRequest,
    user: UserContext = Depends(get_current_owner),
    session: AsyncSession = Depends(get_session),
) -> SlackChannelResponse:
    workspace = await _owned_active_workspace(session, user.org_id)

    if body.service_id is not None:
        owns_service = await session.scalar(
            select(Service.id).where(
                Service.id == body.service_id, Service.org_id == user.org_id
            )
        )
        if owns_service is None:
            raise HTTPException(status_code=404, detail="Service not found")

    # Best-effort join. The bot posts to public channels via chat:write.public
    # without being a member, so a failure here (missing channels:join scope,
    # private channel, already a member) is non-fatal — delivery problems
    # surface later as last_delivery_error.
    try:
        await slack_client.join_channel(_bot_token(workspace), body.slack_channel_id)
    except (slack_client.SlackError, httpx.HTTPError) as exc:
        logger.info("conversations.join skipped for %s: %s", body.slack_channel_id, exc)

    stmt = pg_insert(NotificationChannel).values(
        org_id=user.org_id,
        workspace_id=workspace.id,
        slack_channel_id=body.slack_channel_id,
        slack_channel_name=body.slack_channel_name,
        service_id=body.service_id,
        created_by=user.user_id,
    )
    # Two partial unique indexes back this table (V029), split on service_id
    # NULL vs NOT NULL — pick the matching conflict target.
    if body.service_id is None:
        stmt = stmt.on_conflict_do_update(
            index_elements=["workspace_id", "slack_channel_id"],
            index_where=NotificationChannel.service_id.is_(None),
            set_={"slack_channel_name": body.slack_channel_name, "enabled": True, "last_delivery_error": None},
        )
    else:
        stmt = stmt.on_conflict_do_update(
            index_elements=["workspace_id", "slack_channel_id", "service_id"],
            index_where=NotificationChannel.service_id.is_not(None),
            set_={"slack_channel_name": body.slack_channel_name, "enabled": True, "last_delivery_error": None},
        )
    channel_id = (await session.execute(stmt.returning(NotificationChannel.id))).scalar_one()
    await session.commit()
    logger.info(
        "Slack channel added: org_id=%s channel=%s service_id=%s",
        user.org_id, body.slack_channel_id, body.service_id,
    )
    row = await session.scalar(
        select(NotificationChannel).where(NotificationChannel.id == channel_id)
    )
    return _channel_response(row)


async def _get_channel(session: AsyncSession, channel_id: str, org_id: uuid.UUID) -> NotificationChannel:
    try:
        cid = uuid.UUID(channel_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid channel id") from None
    channel = await session.scalar(
        select(NotificationChannel).where(
            NotificationChannel.id == cid, NotificationChannel.org_id == org_id
        )
    )
    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel


@api_router.delete("/channels/{channel_id}", status_code=204, response_model=None)
async def remove_channel(
    channel_id: str,
    user: UserContext = Depends(get_current_owner),
    session: AsyncSession = Depends(get_session),
) -> None:
    channel = await _get_channel(session, channel_id, user.org_id)
    await session.execute(delete(NotificationChannel).where(NotificationChannel.id == channel.id))
    await session.commit()


@api_router.post("/channels/{channel_id}/test", status_code=204, response_model=None)
async def test_channel(
    channel_id: str,
    user: UserContext = Depends(get_current_owner),
    session: AsyncSession = Depends(get_session),
) -> None:
    channel = await _get_channel(session, channel_id, user.org_id)
    workspace = await _owned_active_workspace(session, user.org_id)
    text = "KubeX is connected — deploy health alerts will arrive here."
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": f":wave: *{text}*"}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": "Test message from Settings → Connections"}]},
    ]
    now = datetime.now(timezone.utc)
    try:
        await slack_client.post_message(
            _bot_token(workspace), channel.slack_channel_id, text, blocks
        )
    except slack_client.SlackError as exc:
        channel.last_delivery_error = exc.code
        await session.commit()
        raise HTTPException(status_code=502, detail=f"Slack rejected the message: {exc.code}") from None
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Could not reach Slack") from None
    channel.last_delivery_at = now
    channel.last_delivery_error = None
    await session.commit()


async def _teardown_workspace(
    session: AsyncSession, team_id: str, *, bot_user_ids: list[str] | None = None
) -> int:
    """Soft-disconnect workspace rows for a Slack team (an org can connect
    the same team, and two KubeX orgs can connect one team). Kept, not
    deleted — the UI shows 'disconnected, reconnect' and an OAuth
    re-install revives the row.

    ``bot_user_ids`` (from a tokens_revoked event) narrows the teardown to
    workspaces whose bot token was actually revoked; None means all
    (app_uninstalled).
    """
    conditions = [
        SlackWorkspace.slack_team_id == team_id,
        SlackWorkspace.uninstalled_at.is_(None),
    ]
    if bot_user_ids is not None:
        conditions.append(SlackWorkspace.bot_user_id.in_(bot_user_ids))
    workspaces = (await session.scalars(select(SlackWorkspace).where(*conditions))).all()
    now = datetime.now(timezone.utc)
    for ws in workspaces:
        ws.uninstalled_at = now
        await session.execute(
            update(NotificationChannel)
            .where(NotificationChannel.workspace_id == ws.id)
            .values(enabled=False, last_delivery_error="workspace disconnected")
        )
    return len(workspaces)


@events_router.post("/events")
async def slack_events(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    body = await verify_slack_signature(request)
    try:
        payload = json.loads(body)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid JSON") from None

    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge", "")}

    if payload.get("type") == "event_callback":
        event = payload.get("event", {})
        event_type = event.get("type")
        team_id = payload.get("team_id")
        if team_id and event_type == "app_uninstalled":
            n = await _teardown_workspace(session, team_id)
            await session.commit()
            logger.info("Slack app_uninstalled for team_id=%s — disconnected %d workspace(s)", team_id, n)
        elif team_id and event_type == "tokens_revoked":
            # Only tear down workspaces whose *bot* token was revoked; a
            # user-token revocation doesn't affect our bot integration.
            revoked_bots = event.get("tokens", {}).get("bot") or []
            if revoked_bots:
                n = await _teardown_workspace(session, team_id, bot_user_ids=revoked_bots)
                await session.commit()
                logger.info(
                    "Slack tokens_revoked for team_id=%s bots=%s — disconnected %d workspace(s)",
                    team_id, revoked_bots, n,
                )

    # Slack retries on any non-2xx; always ack.
    return {"ok": True}
