from __future__ import annotations

import httpx
import pytest

from cluster_agent import ingest_client


@pytest.mark.asyncio
async def test_verify_raises_auth_error_on_401():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="Invalid cluster token")

    ingest_client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://ingest.test"
    )
    with pytest.raises(ingest_client.AuthError):
        await ingest_client.verify()
    await ingest_client.close_client()


@pytest.mark.asyncio
async def test_verify_returns_identity_on_success():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "c1", "name": "my-cluster", "org_id": "o1"})

    ingest_client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://ingest.test"
    )
    identity = await ingest_client.verify()
    assert identity == {"id": "c1", "name": "my-cluster", "org_id": "o1"}
    await ingest_client.close_client()


@pytest.mark.asyncio
async def test_heartbeat_raises_on_other_http_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    ingest_client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://ingest.test"
    )
    with pytest.raises(httpx.HTTPStatusError):
        await ingest_client.heartbeat(
            agent_version="0.1.0", argocd_version=None, argocd_status=None, prometheus_status=None
        )
    await ingest_client.close_client()
