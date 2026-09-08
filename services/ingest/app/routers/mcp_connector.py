"""Public MCP connector endpoint — Streamable HTTP passthrough.

Lets an external MCP client (Claude Desktop, a claude.ai custom
connector, a ChatGPT connector) reach the internal MCP server directly,
the same way a GitHub-style remote MCP server works: point the client
at this URL and paste an org API key (from /settings) in as the bearer
token.

This is a transparent reverse proxy, not a reimplementation of the MCP
protocol — services/mcp-server already speaks Streamable HTTP
correctly and is not reachable from outside the compose network. This
route's only job is authenticating the external caller (the same org
API key already used for the REST API, via verify_api_key) and
translating that into the internal trust boundary
(auth.MCP_INTERNAL_TOKEN + X-Org-Id) mcp_client.py already relies on
for the in-app chat proxy — the external caller's own key is swapped
out before the request ever reaches mcp-server, and mcp-server's own
auth/trust model (services/mcp-server/src/index.ts) is unchanged.
"""

import uuid

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from ..auth import MCP_INTERNAL_TOKEN, verify_api_key
from ..mcp_client import MCP_SERVER_URL

router = APIRouter(tags=["mcp"])

# Only pass through headers relevant to the MCP Streamable HTTP protocol
# itself — notably never the caller's own Authorization, which must not
# reach mcp-server, and never Host, which httpx sets correctly itself.
_FORWARD_REQUEST_HEADERS = {"content-type", "accept", "mcp-session-id", "mcp-protocol-version"}
_FORWARD_RESPONSE_HEADERS = {"content-type", "mcp-session-id"}

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=60.0)
    return _client


@router.api_route("/mcp", methods=["GET", "POST", "DELETE"])
async def mcp_connector(request: Request, org_id: uuid.UUID = Depends(verify_api_key)):
    body = await request.body()
    headers = {k: v for k, v in request.headers.items() if k.lower() in _FORWARD_REQUEST_HEADERS}
    headers["Authorization"] = f"Bearer {MCP_INTERNAL_TOKEN}"
    headers["X-Org-Id"] = str(org_id)

    client = _get_client()
    upstream_request = client.build_request(request.method, MCP_SERVER_URL, content=body, headers=headers)
    upstream = await client.send(upstream_request, stream=True)

    async def body_iterator():
        try:
            async for chunk in upstream.aiter_bytes():
                yield chunk
        finally:
            await upstream.aclose()

    response_headers = {k: v for k, v in upstream.headers.items() if k.lower() in _FORWARD_RESPONSE_HEADERS}
    return StreamingResponse(body_iterator(), status_code=upstream.status_code, headers=response_headers)
