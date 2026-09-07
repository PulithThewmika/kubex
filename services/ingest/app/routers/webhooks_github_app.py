import json
import logging
import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import verify_github_app_signature
from ..correlation.engine import (
    TERMINAL_STATUSES,
    apply_terminal_guarded_status,
    extract_image_tag,
    find_matching_deployment,
    resolve_service,
    terminal_guarded_upsert_set,
    utcnow,
)
from ..db import get_session
from ..models.deployment import Deployment
from ..models.installation import Installation
from ..models.org_membership import OrgMembership
from ..models.organization import Organization
from ..models.pipeline_event import PipelineEvent
from ..models.user import User
from .webhooks_github import process_workflow_run

# GitHub Deployments API states -> DeployLens lifecycle states. "queued" and
# "pending" both mean the deploy hasn't started rolling out yet; DeployLens
# has no separate state for that once the build is done, so both map to
# "syncing" (the same state ArgoCD's on-sync-running maps to). "inactive"
# means a later deployment superseded this one — nothing to record.
DEPLOYMENT_STATE_MAP = {
    "queued": "syncing",
    "pending": "syncing",
    "in_progress": "syncing",
    "success": "deployed",
    "failure": "sync_failed",
    "error": "sync_failed",
}

logger = logging.getLogger("kubex.webhooks.github_app")

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


async def _log_event(
    session: AsyncSession, org_id: uuid.UUID | None, source: str, event_type: str, payload: dict,
) -> None:
    await session.execute(
        PipelineEvent.__table__.insert().values(
            org_id=org_id, source=source, event_type=event_type, payload=payload,
        )
    )


async def _resolve_org_by_github_org_id(session: AsyncSession, github_org_id: int | None) -> uuid.UUID | None:
    if github_org_id is None:
        return None
    result = await session.execute(select(Organization.id).where(Organization.github_org_id == github_org_id))
    return result.scalar_one_or_none()


async def _resolve_org_for_installation_account(session: AsyncSession, account: dict) -> uuid.UUID | None:
    """Resolve the KubeX org a GitHub App installation binds to.

    A GitHub *org* install matches Organization.github_org_id. A *personal
    account* install (account.type == "User") has no github_org_id to match
    — GitHub personal orgs are the auto-created ones with a NULL
    github_org_id (auth.py::_upsert_organization) — so fall back to the
    personal org owned by the user whose github_id is the account id.
    """
    account_id = account.get("id")
    org_id = await _resolve_org_by_github_org_id(session, account_id)
    if org_id is not None or account_id is None:
        return org_id

    if account.get("type") == "User":
        row = (
            await session.execute(
                select(OrgMembership.org_id)
                .join(User, User.id == OrgMembership.user_id)
                .join(Organization, Organization.id == OrgMembership.org_id)
                .where(
                    User.github_id == account_id,
                    OrgMembership.role == "owner",
                    Organization.github_org_id.is_(None),
                )
            )
        ).scalars().all()
        # Only bind when it's unambiguous — a user could own several
        # personal-scoped orgs in theory; guessing one would be a
        # cross-tenant hazard (CLAUDE.md decision 9).
        if len(row) == 1:
            return row[0]
    return None


async def _handle_installation(session: AsyncSession, action: str, payload: dict) -> dict:
    installation_data = payload.get("installation", {})
    github_installation_id = installation_data.get("id")
    account = installation_data.get("account", {})
    account_login = account.get("login", "")

    org_id = await _resolve_org_for_installation_account(session, account)
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
        # On a redelivered/retried "created" (same github_installation_id),
        # only refresh account_login (the one field that can legitimately
        # change, e.g. an account rename) — leaving repos/status alone.
        # Overwriting them here would clobber repos appended since by
        # installation_repositories.added, or reactivate an installation
        # that installation.suspend already turned off.
        stmt = stmt.on_conflict_do_update(
            index_elements=["github_installation_id"],
            set_={"account_login": stmt.excluded.account_login},
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


async def _resolve_org_by_installation_id(
    session: AsyncSession, github_installation_id: int | None,
) -> uuid.UUID | None:
    if github_installation_id is None:
        return None
    result = await session.execute(
        select(Installation.org_id).where(Installation.github_installation_id == github_installation_id)
    )
    return result.scalar_one_or_none()


async def _handle_workflow_run(session: AsyncSession, payload: dict) -> dict:
    github_installation_id = payload.get("installation", {}).get("id")
    repo_full_name = payload.get("repository", {}).get("full_name", "")

    org_id = await _resolve_org_by_installation_id(session, github_installation_id)
    await _log_event(session, org_id, "github_app", "workflow_run", payload)

    if org_id is None:
        logger.warning(
            "workflow_run via unknown installation (github_installation_id=%s), skipping",
            github_installation_id,
        )
        return {"status": "ignored", "reason": "unknown installation"}

    if not repo_full_name:
        return {"status": "ignored", "reason": "missing repository.full_name"}

    return await process_workflow_run(session, org_id, repo_full_name, payload)


async def _handle_deployment_status(session: AsyncSession, payload: dict) -> dict:
    github_installation_id = payload.get("installation", {}).get("id")
    repo_full_name = payload.get("repository", {}).get("full_name", "")
    state = payload.get("deployment_status", {}).get("state")
    commit_sha = payload.get("deployment", {}).get("sha")

    org_id = await _resolve_org_by_installation_id(session, github_installation_id)
    await _log_event(session, org_id, "github_app", "deployment_status", payload)

    if org_id is None:
        logger.warning(
            "deployment_status via unknown installation (github_installation_id=%s), skipping",
            github_installation_id,
        )
        return {"status": "ignored", "reason": "unknown installation"}

    new_status = DEPLOYMENT_STATE_MAP.get(state)
    if new_status is None or not repo_full_name or not commit_sha:
        return {"status": "ignored", "reason": f"deployment_status state '{state}' not handled"}

    service_id, org_id = await resolve_service(session, org_id=org_id, repo=repo_full_name)
    image_tag = extract_image_tag(commit_sha)
    existing, correlation_method = await find_matching_deployment(
        session, service_id, commit_sha=commit_sha, image_tag=image_tag,
    )

    if existing:
        # Out-of-order/redelivered webhooks must not touch a deployment
        # that's already reached a terminal state (deployed/sync_failed) —
        # not a regression back to "syncing", not a flip between the two
        # terminal states, and not even a same-state redelivery (which
        # would otherwise bump finished_at to the redelivery time and
        # change the recorded lifecycle duration). deployment_status
        # carries no ordering signal to tell which event is actually
        # newer. Same class of bug the classic webhook's "completed"
        # handler guards against for ArgoCD/build races.
        applied, persisted_status = await apply_terminal_guarded_status(session, existing.id, new_status)
        if not applied:
            logger.info(
                "Ignoring stale deployment_status '%s' for already-%s deployment_id=%d",
                new_status, persisted_status, existing.id,
            )
            return {"status": "ignored", "reason": f"deployment already {persisted_status}"}

        logger.info(
            "Deployment %s (correlated via %s): service_id=%d deployment_id=%d sha=%s",
            persisted_status, correlation_method, service_id, existing.id, commit_sha,
        )
        return {"status": "ok", "deployment_status": persisted_status, "correlation": correlation_method}

    # V021 added a real ON CONFLICT target (commit_sha, service_id) scoped
    # to workflow_run_id IS NULL — this path never sets workflow_run_id, so
    # a redelivered deployment_status with no prior matching deployment
    # upserts instead of creating a duplicate orphan row.
    stmt = pg_insert(Deployment).values(
        org_id=org_id,
        service_id=service_id,
        commit_sha=commit_sha,
        image_tag=image_tag,
        status=new_status,
        started_at=utcnow(),
        finished_at=utcnow() if new_status in TERMINAL_STATUSES else None,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["commit_sha", "service_id"],
        index_where=Deployment.commit_sha.is_not(None) & Deployment.workflow_run_id.is_(None),
        set_=terminal_guarded_upsert_set(new_status),
    ).returning(Deployment.status)
    # The terminal-state guard above can mean the row that actually landed
    # keeps its pre-existing status rather than new_status (a concurrent
    # first-time delivery raced this one and got there first) — report
    # what was actually persisted.
    persisted_status = (await session.execute(stmt)).scalar_one()
    logger.info(
        "Orphan deployment created/upserted (%s): service_id=%d sha=%s repo=%s",
        persisted_status, service_id, commit_sha, repo_full_name,
    )
    return {"status": "ok", "deployment_status": persisted_status, "correlation": "orphan"}


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
