from __future__ import annotations

from pydantic import AnyHttpUrl, BaseModel, Field


class HealthCheckConfigRequest(BaseModel):
    health_check_url: AnyHttpUrl
    health_check_interval_s: int = Field(default=30, ge=5, le=3600)


class HealthCheckConfigResponse(BaseModel):
    name: str
    health_check_url: str
    health_check_interval_s: int
