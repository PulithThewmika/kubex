"""MCP client helper for the chat proxy.

The KubeX MCP server (services/mcp-server) runs as its own
docker-compose container with no shared process or filesystem with
ingest, so the stdio transport it uses for local/CLI usage doesn't
reach it. In http mode (MCP_TRANSPORT=http) it exposes a Streamable
HTTP endpoint instead — see services/mcp-server/src/index.ts.

The server runs that transport in stateless mode (sessionIdGenerator
undefined), so there's no long-lived session to keep alive: each call
here opens a fresh MCP session, does its work, and tears down.
"""

import logging
import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

logger = logging.getLogger("kubex.ingest.mcp_client")

MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://mcp-server:3001/mcp")
MCP_INTERNAL_TOKEN = os.environ.get("MCP_INTERNAL_TOKEN", "")


@asynccontextmanager
async def mcp_session(org_id: uuid.UUID) -> AsyncIterator[ClientSession]:
    """Open a short-lived, initialized MCP session against the KubeX MCP server.

    org_id is passed as an X-Org-Id header so the MCP server can scope its
    tool calls to the caller's org (E20-T3 enforces this server-side).
    The Authorization bearer token authenticates ingest itself to the MCP
    server -- same shared-token pattern as ARGOCD_WEBHOOK_TOKEN /
    ALERTMANAGER_WEBHOOK_TOKEN in app/auth.py -- so X-Org-Id can't be
    forged by some other caller on the compose network.
    """
    headers = {"X-Org-Id": str(org_id), "Authorization": f"Bearer {MCP_INTERNAL_TOKEN}"}
    async with create_mcp_http_client(headers=headers) as http_client:
        async with streamable_http_client(MCP_SERVER_URL, http_client=http_client) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session
