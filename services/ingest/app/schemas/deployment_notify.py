"""Schemas for POST /api/deployments/notify (E21-T3-S3), the generic deploy
notification endpoint for customers with no GitHub Actions/ArgoCD
integration."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

# Strips surrounding whitespace before enforcing min_length, so " " isn't
# accepted as a non-blank service name/commit sha.
NonBlankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class DeploymentNotifyRequest(BaseModel):
    service: NonBlankStr
    commit_sha: NonBlankStr
    status: Literal["pending", "in_progress", "success", "failure", "error"]
    environment: str | None = None
    image_tag: str | None = None


class DeploymentNotifyResponse(BaseModel):
    status: str
    deployment_id: int | None = None
    deployment_status: str | None = None
    correlation: str
