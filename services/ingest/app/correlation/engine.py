import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import case, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.deployment import Deployment
from ..models.organization import Organization
from ..models.service import Service

logger = logging.getLogger("kubex.correlation")

# Once a deployment reaches one of these, no further event for it should
# regress it back to an in-progress state or flip it to the other terminal
# state — the event sources that report status here (GitHub Deployments
# API, the generic notify endpoint) carry no ordering signal to tell which
# delivery is actually the newer one.
TERMINAL_STATUSES = ("deployed", "sync_failed")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def apply_terminal_guarded_status(
    session: AsyncSession, deployment_id: int, new_status: str,
) -> tuple[bool, str]:
    """Transition a deployment's status via a WHERE-guarded UPDATE ...
    RETURNING, rather than mutating an already-loaded ORM object in
    place. Mutating in place and committing would issue an unconditional
    UPDATE that can overwrite a status a *concurrent* transaction already
    committed to terminal between this request's correlating SELECT and
    this call (/code-review high on PR #796 fixed the same class of race
    for the ON CONFLICT path via SQL CASE; this closes it for the
    existing-row path too). Returns (applied, persisted_status) — when
    not applied, persisted_status is the real current value, re-queried,
    for accurate logging/response reporting."""
    values = {"status": new_status}
    if new_status in TERMINAL_STATUSES:
        values["finished_at"] = utcnow()
    stmt = (
        update(Deployment)
        .where(Deployment.id == deployment_id, Deployment.status.not_in(TERMINAL_STATUSES))
        .values(**values)
        .returning(Deployment.status)
    )
    persisted = (await session.execute(stmt)).scalar_one_or_none()
    if persisted is not None:
        return True, persisted

    result = await session.execute(select(Deployment.status).where(Deployment.id == deployment_id))
    return False, result.scalar_one()


def terminal_guarded_upsert_set(new_status: str, extra: dict | None = None) -> dict:
    """The `set_` dict for an ON CONFLICT DO UPDATE that must not regress a
    row already in a terminal state — same guard as
    apply_terminal_guarded_status, expressed as SQL CASE so it holds even
    under a race between two concurrent first-time deliveries."""
    set_ = {
        "status": case(
            (Deployment.status.in_(TERMINAL_STATUSES), Deployment.status),
            else_=new_status,
        ),
        "finished_at": case(
            (Deployment.status.in_(TERMINAL_STATUSES), Deployment.finished_at),
            else_=(utcnow() if new_status in TERMINAL_STATUSES else Deployment.finished_at),
        ),
    }
    if extra:
        set_.update(extra)
    return set_


def parse_iso_timestamp(ts: str | None) -> datetime | None:
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def extract_image_tag(head_sha: str | None) -> str | None:
    if head_sha and len(head_sha) >= 7:
        return head_sha[:7]
    return head_sha


def extract_image_tag_from_images(images_str: str | None) -> str | None:
    """Extract the short image tag from ArgoCD's summary.images field.

    ArgoCD renders summary.images as a comma-separated string of image
    references (e.g. "ghcr.io/org/app-frontend:abc1234,ghcr.io/org/app-orders:abc1234").
    All images in a single sync share the same tag, so we take the first one.
    Returns None if the string is empty or contains no parseable tag.
    """
    if not images_str or not images_str.strip():
        return None
    first_image = images_str.split(",")[0].strip().strip("[]")
    if ":" not in first_image:
        return None
    tag = first_image.rsplit(":", 1)[1]
    if not tag or tag == "latest":
        return None
    return tag


@dataclass
class CorrelationResult:
    deployment: Deployment
    service_id: int
    method: str  # "commit_sha", "image_tag", "orphan", "new"
    is_new: bool


async def get_default_org_id(session: AsyncSession) -> uuid.UUID:
    """Fallback org for a service with no other org signal to resolve from.

    GitHub/ArgoCD webhooks authenticate with one global shared secret
    today (GITHUB_WEBHOOK_SECRET / ARGOCD_WEBHOOK_TOKEN) — there is no
    per-org signal in the request at all. Falls back to the oldest
    organization row, the same one V014 backfilled all pre-multi-tenancy
    data to.
    # ponytail: single global default-org fallback for auto-registration,
    # correct only while webhooks share one secret; upgrade when webhooks
    # carry a per-org secret/token that identifies the calling org directly.
    """
    result = await session.execute(
        select(Organization.id).order_by(Organization.created_at.asc()).limit(1)
    )
    org_id = result.scalar_one_or_none()
    if org_id is None:
        raise RuntimeError("No organizations exist — cannot resolve a default org")
    return org_id


async def resolve_org_id(
    session: AsyncSession,
    *,
    repo: str | None = None,
    argocd_app: str | None = None,
) -> uuid.UUID:
    """Read-only org lookup, for events that must not auto-register a service.

    Used to stamp org_id on pipeline_events rows for event types that
    resolve_service() never sees (e.g. non-workflow_run GitHub events) —
    matches an existing service's org if one exists, else the default org.
    # ponytail: webhook handlers that go on to call resolve_service() for
    # the same repo/argocd_app pay two lookups instead of one for the
    # common case of an already-known service, to keep this read-only
    # path from ever triggering resolve_service()'s auto-registration
    # side effect. Upgrade to a single combined lookup if webhook volume
    # ever makes the extra indexed SELECT per delivery matter.
    #
    # This repo/argocd_app match relies on repo (GitHub owner/repo) and
    # argocd_app (one app name per cluster) being de-facto globally unique —
    # true today, but V018 (#792) made (org_id, repo)/(org_id, argocd_app)
    # uniqueness org-scoped rather than global, so two orgs sharing a repo
    # is now schema-legal. Rather than silently picking whichever org has
    # the lower services.id (misattributing the event), fail loudly on that
    # ambiguity — same "refuse to guess" convention as V014's backfill
    # guard.
    # ponytail: full fix is trusting the caller's own org identity instead
    # of inferring it from repo/argocd_app at all — the natural point for
    # that is EPIC-021's per-installation org identification, not this
    # read-only lookup.
    """
    if repo:
        result = await session.execute(select(Service.org_id).where(Service.repo == repo).distinct())
        org_ids = result.scalars().all()
        if len(org_ids) > 1:
            raise RuntimeError(
                f"repo '{repo}' is registered under multiple orgs ({org_ids}) — ambiguous, refusing to guess"
            )
        if org_ids:
            return org_ids[0]

    if argocd_app:
        result = await session.execute(select(Service.org_id).where(Service.argocd_app == argocd_app).distinct())
        org_ids = result.scalars().all()
        if len(org_ids) > 1:
            raise RuntimeError(
                f"argocd_app '{argocd_app}' is registered under multiple orgs ({org_ids}) — ambiguous, refusing to guess"
            )
        if org_ids:
            return org_ids[0]

    return await get_default_org_id(session)


async def resolve_service(
    session: AsyncSession,
    *,
    org_id: uuid.UUID,
    repo: str | None = None,
    argocd_app: str | None = None,
    name: str | None = None,
) -> tuple[int, uuid.UUID]:
    # org_id is the caller's already-resolved org for this event (today,
    # always resolve_org_id()'s result — the default org, since webhooks
    # share one secret; once EPIC-021 identifies the org per GitHub App
    # installation, callers pass that instead). Every lookup below is
    # scoped to it: repo and argocd_app are effectively globally unique
    # (GitHub owner/repo, one ArgoCD app name per cluster) so matching on
    # them without the scope would still be safe, but the name fallback is
    # not — two orgs can derive the same `name` from different repos, and
    # without this scope it would match (and mis-attribute to) another
    # org's row. See #792.
    if repo:
        result = await session.execute(
            select(Service)
            .where(Service.repo == repo, Service.org_id == org_id)
            .order_by(Service.id)
        )
        services = result.scalars().all()
        if services:
            if len(services) > 1:
                # No unique constraint on repo, so a repo-migration seed
                # update (see V011) racing an auto-registration can leave two
                # rows pointing at the same repo. Prefer the oldest rather
                # than crash the webhook on this - manual reconciliation
                # (merge/delete the newer row) is still needed.
                logger.warning(
                    "Multiple services share repo='%s' (ids=%s) — using oldest (id=%d); "
                    "manual reconciliation needed",
                    repo, [s.id for s in services], services[0].id,
                )
            return services[0].id, services[0].org_id

    if argocd_app:
        result = await session.execute(
            select(Service)
            .where(Service.argocd_app == argocd_app, Service.org_id == org_id)
            .order_by(Service.id)
        )
        services = result.scalars().all()
        if services:
            if len(services) > 1:
                logger.warning(
                    "Multiple services share argocd_app='%s' (ids=%s) — using oldest (id=%d); "
                    "manual reconciliation needed",
                    argocd_app, [s.id for s in services], services[0].id,
                )
            return services[0].id, services[0].org_id

    # `name` lets callers with no repo/argocd_app (e.g. the generic deploy
    # notification endpoint, E21-T3) resolve/register a service directly by
    # name instead of deriving one from a GitHub repo or ArgoCD app.
    name = name or (
        repo.split("/")[-1] if repo
        else argocd_app if argocd_app
        else "unknown"
    )

    result = await session.execute(
        select(Service).where(Service.name == name, Service.org_id == org_id)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        if repo and not existing.repo:
            existing.repo = repo
            logger.info("Linked repo '%s' to existing service '%s' (id=%d)", repo, name, existing.id)
        if argocd_app and not existing.argocd_app:
            existing.argocd_app = argocd_app
            logger.info("Linked ArgoCD app '%s' to existing service '%s' (id=%d)", argocd_app, name, existing.id)
        await session.flush()
        return existing.id, existing.org_id

    service = Service(name=name, repo=repo, argocd_app=argocd_app, org_id=org_id)
    try:
        async with session.begin_nested():
            session.add(service)
            await session.flush()
    except IntegrityError:
        # Lost a race with a concurrent request auto-registering the same
        # (org_id, name)/(org_id, repo)/(org_id, argocd_app) between this
        # function's lookup above and this flush — the other request's row
        # already exists (uq_services_org_name/_repo/_argocd_app), so reuse
        # it instead of erroring. Most likely to bite the generic notify
        # endpoint (E21-T3), which can register a brand-new service name
        # from a burst of concurrent first deliveries.
        #
        # No session.expunge(service) here: rolling back to the savepoint
        # on this IntegrityError already evicts `service` back to the
        # transient state (it never became persistent), so expunging it
        # again would raise InvalidRequestError instead of letting this
        # recovery path run (CodeRabbit, PR #796).
        result = await session.execute(
            select(Service).where(Service.name == name, Service.org_id == org_id)
        )
        existing = result.scalar_one()
        logger.info(
            "Lost service auto-registration race for '%s' (org_id=%s) — reusing id=%d",
            name, org_id, existing.id,
        )
        return existing.id, existing.org_id

    logger.info(
        "Auto-registered service '%s' (id=%d, repo=%s, argocd_app=%s, org_id=%s)",
        name, service.id, repo, argocd_app, org_id,
    )
    return service.id, org_id


async def find_matching_deployment(
    session: AsyncSession,
    service_id: int,
    *,
    commit_sha: str | None = None,
    image_tag: str | None = None,
) -> tuple[Deployment | None, str]:
    if commit_sha:
        result = await session.execute(
            select(Deployment)
            .where(Deployment.service_id == service_id, Deployment.commit_sha == commit_sha)
            .order_by(Deployment.created_at.desc())
            .limit(1)
        )
        deployment = result.scalar_one_or_none()
        if deployment is not None:
            logger.info(
                "Correlated via commit_sha: deployment_id=%d service_id=%d sha=%s",
                deployment.id, service_id, commit_sha,
            )
            return deployment, "commit_sha"

    if image_tag:
        short_tag = image_tag[:7] if len(image_tag) >= 7 else image_tag
        result = await session.execute(
            select(Deployment)
            .where(Deployment.service_id == service_id, Deployment.image_tag == short_tag)
            .order_by(Deployment.created_at.desc())
            .limit(1)
        )
        deployment = result.scalar_one_or_none()
        if deployment is not None:
            logger.info(
                "Correlated via image_tag fallback: deployment_id=%d service_id=%d tag=%s",
                deployment.id, service_id, short_tag,
            )
            return deployment, "image_tag"

    logger.info(
        "No matching deployment found: service_id=%d sha=%s tag=%s",
        service_id, commit_sha, image_tag,
    )
    return None, "none"
