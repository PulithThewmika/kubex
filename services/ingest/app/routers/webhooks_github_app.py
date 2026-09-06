import json
import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import verify_github_app_signature
from ..db import get_session
from ..models.pipeline_event import PipelineEvent

logger = logging.getLogger("kubex.webhooks.github_app")

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


async def _log_event(session: AsyncSession, org_id, source: str, event_type: str, payload: dict) -> None:
    await session.execute(
        PipelineEvent.__table__.insert().values(
            org_id=org_id, source=source, event_type=event_type, payload=payload,
        )
    )


async def _handle_installation(session: AsyncSession, action: str, payload: dict) -> dict:
    return {"status": "ignored", "reason": f"installation action '{action}' not handled"}


async def _handle_installation_repositories(session: AsyncSession, action: str, payload: dict) -> dict:
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
