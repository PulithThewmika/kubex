"""Schemas for POST /api/deployments/notify (E21-T3-S3), the generic deploy
notification endpoint for customers with no GitHub Actions/ArgoCD
integration."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class DeploymentNotifyRequest(BaseModel):
    service: str
    commit_sha: str
    status: Literal["pending", "in_progress", "success", "failure", "error"]
    environment: str | None = None
    image_tag: str | None = None


class DeploymentNotifyResponse(BaseModel):
    status: str
    deployment_id: int | None = None
    deployment_status: str | None = None
    correlation: str
