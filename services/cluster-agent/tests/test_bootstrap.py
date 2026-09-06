from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from cluster_agent import bootstrap, ingest_client


@pytest.mark.asyncio
async def test_verify_identity_returns_verified_cluster() -> None:
    identity = {"id": "c1", "name": "my-cluster", "org_id": "o1"}
    with (
        patch("cluster_agent.bootstrap.validate", lambda: None),
        patch("cluster_agent.ingest_client.verify", AsyncMock(return_value=identity)),
    ):
        result = await bootstrap.verify_identity()
    assert result == identity


@pytest.mark.asyncio
async def test_verify_identity_propagates_auth_error() -> None:
    with (
        patch("cluster_agent.bootstrap.validate", lambda: None),
        patch("cluster_agent.ingest_client.verify", AsyncMock(side_effect=ingest_client.AuthError("bad token"))),
    ):
        with pytest.raises(ingest_client.AuthError):
            await bootstrap.verify_identity()
