"""Tests for /mcp — the public MCP connector passthrough (external
clients like Claude Desktop/claude.ai/ChatGPT, authenticated with an
org API key instead of the internal MCP_INTERNAL_TOKEN)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth import verify_api_key
from app.main import app

TEST_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


def _mock_upstream(status_code: int = 200, content_type: str = "application/json", chunks=None) -> MagicMock:
    chunks = chunks or [b'{"result": "ok"}']
    upstream = MagicMock()
    upstream.status_code = status_code
    upstream.headers = {"content-type": content_type} if content_type else {}
    upstream.aclose = AsyncMock()

    async def aiter_bytes():
        for chunk in chunks:
            yield chunk

    upstream.aiter_bytes = aiter_bytes
    return upstream


def _mock_mcp_client(upstream=None) -> MagicMock:
    c = MagicMock()
    c.build_request = MagicMock(return_value="fake-request")
    c.send = AsyncMock(return_value=upstream or _mock_upstream())
    return c


@pytest.fixture
def api_key_client():
    async def override_verify_api_key():
        return TEST_ORG_ID

    app.dependency_overrides[verify_api_key] = override_verify_api_key
    yield app
    app.dependency_overrides.pop(verify_api_key, None)


@pytest.mark.asyncio
async def test_mcp_connector_requires_api_key():
    """No auth override — the real verify_api_key dependency should 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/mcp", json={"jsonrpc": "2.0", "method": "tools/list", "id": 1})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_mcp_connector_forwards_to_internal_server(api_key_client):
    mcp_client = _mock_mcp_client()
    with (
        patch("app.routers.mcp_connector._get_client", return_value=mcp_client),
        patch("app.routers.mcp_connector.MCP_INTERNAL_TOKEN", "internal-secret"),
        patch("app.routers.mcp_connector.MCP_SERVER_URL", "http://mcp-server:3001/mcp"),
    ):
        async with AsyncClient(transport=ASGITransport(app=api_key_client), base_url="http://test") as ac:
            resp = await ac.post(
                "/mcp",
                json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
                headers={"Authorization": "Bearer org-api-key-value"},
            )

    assert resp.status_code == 200
    assert resp.content == b'{"result": "ok"}'

    method, url = mcp_client.build_request.call_args.args[:2]
    headers = mcp_client.build_request.call_args.kwargs["headers"]
    assert method == "POST"
    assert url == "http://mcp-server:3001/mcp"
    # The caller's own org API key must never reach the internal server —
    # it's swapped for the internal trust token, and X-Org-Id is set from
    # the verified org, not any client-supplied header.
    assert headers["Authorization"] == "Bearer internal-secret"
    assert "org-api-key-value" not in headers["Authorization"]
    assert headers["X-Org-Id"] == str(TEST_ORG_ID)


@pytest.mark.asyncio
async def test_mcp_connector_streams_response_body(api_key_client):
    upstream = _mock_upstream(chunks=[b"chunk1", b"chunk2", b"chunk3"])
    mcp_client = _mock_mcp_client(upstream)
    with patch("app.routers.mcp_connector._get_client", return_value=mcp_client):
        async with AsyncClient(transport=ASGITransport(app=api_key_client), base_url="http://test") as ac:
            resp = await ac.post("/mcp", json={"jsonrpc": "2.0", "method": "tools/list", "id": 1})

    assert resp.content == b"chunk1chunk2chunk3"
    upstream.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_mcp_connector_passes_through_upstream_status_and_content_type(api_key_client):
    upstream = _mock_upstream(status_code=400, content_type="application/json", chunks=[b'{"error": "bad"}'])
    mcp_client = _mock_mcp_client(upstream)
    with patch("app.routers.mcp_connector._get_client", return_value=mcp_client):
        async with AsyncClient(transport=ASGITransport(app=api_key_client), base_url="http://test") as ac:
            resp = await ac.post("/mcp", json={"jsonrpc": "2.0", "method": "bogus", "id": 1})

    assert resp.status_code == 400
    assert resp.headers["content-type"] == "application/json"


@pytest.mark.asyncio
async def test_mcp_connector_forwards_mcp_session_id_header(api_key_client):
    mcp_client = _mock_mcp_client()
    with patch("app.routers.mcp_connector._get_client", return_value=mcp_client):
        async with AsyncClient(transport=ASGITransport(app=api_key_client), base_url="http://test") as ac:
            await ac.post(
                "/mcp",
                json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
                headers={"Mcp-Session-Id": "session-abc"},
            )

    headers = mcp_client.build_request.call_args.kwargs["headers"]
    assert headers["mcp-session-id"] == "session-abc"
