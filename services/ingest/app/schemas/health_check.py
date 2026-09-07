from __future__ import annotations

from ipaddress import ip_address
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

from ..auth import ALLOW_INSECURE_HEALTH_CHECK_URL

# Detection agent pings on a fixed HEALTH_CHECK_TICK_SECONDS tick
# (services/agent/agent/config.py, default 15s) — an interval below that
# would silently round up to it, so the floor here matches that default
# rather than promising a cadence the agent can't actually deliver.
MIN_HEALTH_CHECK_INTERVAL_S = 15


def _is_loopback_or_link_local(host: str) -> bool:
    # ponytail: checks the literal hostname, same as install.py's
    # INGEST_PUBLIC_URL guard — doesn't resolve DNS, so a rebinding attack
    # (a hostname that resolves to 169.254.169.254 only after this check
    # runs) still slips through. Upgrade path: validate the resolved
    # socket address at connection time in the agent's ping(), not just
    # the configured string here.
    if host == "localhost":
        return True
    try:
        addr = ip_address(host)
        return addr.is_loopback or addr.is_link_local
    except ValueError:
        return False


class HealthCheckConfigRequest(BaseModel):
    health_check_url: str
    health_check_interval_s: int = Field(default=30, ge=MIN_HEALTH_CHECK_INTERVAL_S, le=3600)

    @field_validator("health_check_url")
    @classmethod
    def _validate_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError("health_check_url must be an http:// or https:// URL")
        if not ALLOW_INSECURE_HEALTH_CHECK_URL and _is_loopback_or_link_local(parsed.hostname):
            raise ValueError(
                "health_check_url must not be a loopback or link-local address "
                "(set ALLOW_INSECURE_HEALTH_CHECK_URL=true for local/dev only)"
            )
        return value


class HealthCheckConfigResponse(BaseModel):
    name: str
    health_check_url: str
    health_check_interval_s: int
