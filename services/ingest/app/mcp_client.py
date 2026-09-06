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


@asynccontextmanager
async def mcp_session(org_id: uuid.UUID) -> AsyncIterator[ClientSession]:
    """Open a short-lived, initialized MCP session against the KubeX MCP server.

    org_id is passed as an X-Org-Id header so the MCP server can scope
    its tool calls to the caller's org. Full server-side enforcement of
    this header is E20-T3's scope -- this just plumbs it through.
    """
    async with create_mcp_http_client(headers={"X-Org-Id": str(org_id)}) as http_client:
        async with streamable_http_client(MCP_SERVER_URL, http_client=http_client) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session
