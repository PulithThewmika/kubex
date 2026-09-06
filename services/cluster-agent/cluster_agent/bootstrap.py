"""Agent bootstrap (E22-T3-S2).

Reads CLUSTER_TOKEN/DEPLOYLENS_ENDPOINT from the environment (populated by
the install manifest's Secret + env — see install.py's build_install_manifest)
and validates them against POST /api/clusters/verify before the agent does
anything else.
"""

from __future__ import annotations

import logging

from . import ingest_client
from .config import validate

logger = logging.getLogger("kubex.cluster_agent.bootstrap")


async def verify_identity() -> dict:
    """Validate the cluster token. Returns the verified identity
    ({id, name, org_id}) or raises: RuntimeError if required env vars are
    unset, ingest_client.AuthError if the token itself is rejected."""
    validate()
    identity = await ingest_client.verify()
    logger.info("Verified as cluster %s (%s) in org %s", identity["id"], identity["name"], identity["org_id"])
    return identity
