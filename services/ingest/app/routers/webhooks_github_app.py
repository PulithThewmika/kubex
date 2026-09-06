import json
import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import verify_github_app_signature
from ..correlation.engine import resolve_service
from ..db import get_session
from ..models.installation import Installation
from ..models.organization import Organization
from ..models.pipeline_event import PipelineEvent

logger = logging.getLogger("kubex.webhooks.github_app")

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


async def _log_event(session: AsyncSession, org_id, source: str, event_type: str, payload: dict) -> None:
    await session.execute(
        PipelineEvent.__table__.insert().values(
            org_id=org_id, source=source, event_type=event_type, payload=payload,
        )
    )


async def _resolve_org_by_github_org_id(session: AsyncSession, github_org_id: int | None):
    if github_org_id is None:
        return None
    result = await session.execute(select(Organization.id).where(Organization.github_org_id == github_org_id))
    return result.scalar_one_or_none()


async def _handle_installation(session: AsyncSession, action: str, payload: dict) -> dict:
    installation_data = payload.get("installation", {})
    github_installation_id = installation_data.get("id")
    account = installation_data.get("account", {})
    account_login = account.get("login", "")

    org_id = await _resolve_org_by_github_org_id(session, account.get("id"))
    await _log_event(session, org_id, "github_app", "installation", payload)

    if org_id is None:
        logger.warning(
            "installation.%s for unknown account (github_account_id=%s, login=%s) — "
            "no organization has logged in with this GitHub account yet, skipping",
            action, account.get("id"), account_login,
        )
        return {"status": "ignored", "reason": "no organization matches this GitHub account"}

    if action == "created":
        repos = [r["full_name"] for r in payload.get("repositories", []) if r.get("full_name")]
        stmt = pg_insert(Installation).values(
            org_id=org_id,
            github_installation_id=github_installation_id,
            account_login=account_login,
            repos=repos,
            status="active",
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["github_installation_id"],
            set_={
                "org_id": stmt.excluded.org_id,
                "account_login": stmt.excluded.account_login,
                "repos": stmt.excluded.repos,
                "status": "active",
            },
        )
        await session.execute(stmt)
        logger.info(
            "Installation created: github_installation_id=%s org_id=%s account=%s repos=%s",
            github_installation_id, org_id, account_login, repos,
        )
        return {"status": "ok", "installation": "created"}

    if action == "deleted":
        # Mark removed rather than delete the row — its org_id/repos stay
        # around for historical deployments that still reference it.
        await session.execute(
            update(Installation)
            .where(Installation.github_installation_id == github_installation_id)
            .values(status="removed")
        )
        logger.info("Installation removed: github_installation_id=%s org_id=%s", github_installation_id, org_id)
        return {"status": "ok", "installation": "removed"}

    if action in ("suspend", "unsuspend"):
        new_status = "suspended" if action == "suspend" else "active"
        await session.execute(
            update(Installation)
            .where(Installation.github_installation_id == github_installation_id)
            .values(status=new_status)
        )
        logger.info(
            "Installation %s: github_installation_id=%s org_id=%s",
            new_status, github_installation_id, org_id,
        )
        return {"status": "ok", "installation": new_status}

    return {"status": "ignored", "reason": f"installation action '{action}' not handled"}


async def _handle_installation_repositories(session: AsyncSession, action: str, payload: dict) -> dict:
    github_installation_id = payload.get("installation", {}).get("id")

    result = await session.execute(
        select(Installation).where(Installation.github_installation_id == github_installation_id)
    )
    installation = result.scalar_one_or_none()

    await _log_event(
        session, installation.org_id if installation else None,
        "github_app", "installation_repositories", payload,
    )

    if installation is None:
        logger.warning(
            "installation_repositories.%s for unknown installation (github_installation_id=%s)",
            action, github_installation_id,
        )
        return {"status": "ignored", "reason": "unknown installation"}

    if action == "added":
        added = [r["full_name"] for r in payload.get("repositories_added", []) if r.get("full_name")]
        for repo in added:
            if repo not in installation.repos:
                installation.repos.append(repo)
            await resolve_service(session, org_id=installation.org_id, repo=repo)
        logger.info(
            "Installation repos added: github_installation_id=%s org_id=%s repos=%s",
            github_installation_id, installation.org_id, added,
        )
        return {"status": "ok", "repos_added": added}

    if action == "removed":
        removed = [r["full_name"] for r in payload.get("repositories_removed", []) if r.get("full_name")]
        installation.repos = [r for r in installation.repos if r not in removed]
        logger.info(
            "Installation repos removed: github_installation_id=%s org_id=%s repos=%s",
            github_installation_id, installation.org_id, removed,
        )
        return {"status": "ok", "repos_removed": removed}

    return {"status": "ignored", "reason": f"installation_repositories action '{action}' not handled"}


async def _handle_workflow_run(session: AsyncSession, payload: dict) -> dict:
    return {"status": "ignored", "reason": "workflow_run via GitHub App not yet handled"}


async def _handle_deployment_status(session: AsyncSession, payload: dict) -> dict:
    return {"status": "ignored", "reason": "deployment_status not yet handled"}


@router.post("/github/app")
async def github_app_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    body = await verify_github_app_signature(request)
    payload = json.loads(body)
    event_type = request.headers.get("X-GitHub-Event", "unknown")
    action = payload.get("action")

    if event_type == "installation":
        result = await _handle_installation(session, action, payload)
    elif event_type == "installation_repositories":
        result = await _handle_installation_repositories(session, action, payload)
    elif event_type == "workflow_run":
        result = await _handle_workflow_run(session, payload)
    elif event_type == "deployment_status":
        result = await _handle_deployment_status(session, payload)
    else:
        await _log_event(session, None, "github_app", event_type, payload)
        await session.commit()
        logger.info("Received unhandled GitHub App event '%s'", event_type)
        return {"status": "ignored", "reason": f"event type '{event_type}' not handled"}

    await session.commit()
    return result
