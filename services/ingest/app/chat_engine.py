"""Core agentic chat loop: Gemini API + MCP tool calling.

One call to run_chat_turn() handles a full turn, including any number
of tool-use round trips: stream text deltas, and whenever Gemini asks
for a tool, call it via MCP, stream the result, and feed it back until
Gemini produces a final answer (or the iteration cap is hit).
"""

import asyncio
import json
import logging
import os
import uuid
from collections.abc import AsyncIterator

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from .chat_prompt import SYSTEM_PROMPT
from .mcp_client import mcp_session
from .schemas.chat import ChatMessage

logger = logging.getLogger("kubex.ingest.chat_engine")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
CHAT_MODEL = os.environ.get("CHAT_MODEL", "gemini-flash-latest")
MAX_TOKENS = 1024
# Guards against a runaway tool-call loop (a model that never stops calling tools).
MAX_TOOL_ITERATIONS = 8

# Gemini's free tier returns these under transient load (observed live,
# 2026-09-08: two straight 503 UNAVAILABLE "high demand" responses before a
# third attempt succeeded) — worth a short retry rather than failing the
# whole chat turn on a moment's congestion. 429 (rate limit) gets the same
# treatment. Anything else (400 bad request, 401/403 auth) fails immediately
# — retrying those just wastes the user's wait on an error that won't change.
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 2  # up to 3 attempts total
_RETRY_BASE_DELAY_SECONDS = 1.0


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def list_gemini_tools(org_id: uuid.UUID) -> list[dict]:
    """Fetch the MCP tool list and convert it to Gemini's function-declaration schema.

    parameters_json_schema takes the MCP tool's JSON Schema as-is — unlike
    the stricter OpenAPI-subset `parameters` field, Gemini accepts a real
    JSON Schema here directly, so no sanitizing/stripping of MCP's
    zod-to-json-schema output is needed.
    """
    async with mcp_session(org_id) as session:
        result = await session.list_tools()
        return [
            {
                "name": tool.name,
                "description": tool.description or "",
                "parameters_json_schema": tool.input_schema,
            }
            for tool in result.tools
        ]


async def _call_mcp_tool(org_id: uuid.UUID, name: str, arguments: dict) -> tuple[str, bool]:
    async with mcp_session(org_id) as session:
        result = await session.call_tool(name, arguments)
        text = "".join(
            block.text for block in result.content if getattr(block, "text", None)
        )
        return text or "(empty tool result)", result.is_error


def _to_gemini_contents(messages: list[ChatMessage]) -> list[types.Content]:
    return [
        types.Content(
            role="model" if m.role == "assistant" else "user",
            parts=[types.Part.from_text(text=m.content)],
        )
        for m in messages
    ]


async def run_chat_turn(
    messages: list[ChatMessage], tools: list[dict], org_id: uuid.UUID
) -> AsyncIterator[str]:
    """Run one agentic chat turn, yielding SSE frames.

    `tools` is passed in (rather than fetched here) so the caller can
    do the MCP-connectivity pre-flight check before committing to a
    streaming response — see routers/chat.py.
    """
    client = genai.Client(api_key=GEMINI_API_KEY)
    current_contents = _to_gemini_contents(messages)
    function_declarations = [types.FunctionDeclaration(**t) for t in tools]
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        max_output_tokens=MAX_TOKENS,
        tools=[types.Tool(function_declarations=function_declarations)] if function_declarations else None,
    )

    for _ in range(MAX_TOOL_ITERATIONS):
        sent_any_output = False
        for retry_attempt in range(_MAX_RETRIES + 1):
            accumulated_parts: list[types.Part] = []
            try:
                stream = await client.aio.models.generate_content_stream(
                    model=CHAT_MODEL,
                    contents=current_contents,
                    config=config,
                )
                async for chunk in stream:
                    if chunk.text:
                        sent_any_output = True
                        yield sse("text", {"text": chunk.text})
                    if chunk.candidates and chunk.candidates[0].content:
                        accumulated_parts.extend(chunk.candidates[0].content.parts or [])
                break  # success — stop retrying
            except genai_errors.APIError as e:
                # Only retry a clean failure with nothing sent yet this
                # attempt — once any text has reached the client, headers
                # and partial content are already committed, so retrying
                # would duplicate output rather than replace it.
                if e.code in _RETRYABLE_STATUS_CODES and not sent_any_output and retry_attempt < _MAX_RETRIES:
                    delay = _RETRY_BASE_DELAY_SECONDS * (2**retry_attempt)
                    logger.warning(
                        "Gemini API error %s, retrying in %.1fs (attempt %d/%d)",
                        e.code, delay, retry_attempt + 1, _MAX_RETRIES,
                    )
                    await asyncio.sleep(delay)
                    continue
                logger.exception("Gemini API error mid-stream")
                yield sse("error", {"error": "LLM service unavailable"})
                return
            except Exception:
                # Headers are already committed to 200 by the time we're
                # streaming, so a mid-stream LLM failure can't become an
                # HTTP 502 — it becomes part of the stream instead. A
                # pre-flight check in routers/chat.py catches the common
                # case (missing API key) before the response starts.
                logger.exception("Gemini API error mid-stream")
                yield sse("error", {"error": "LLM service unavailable"})
                return

        current_contents.append(types.Content(role="model", parts=accumulated_parts))

        function_calls = [p.function_call for p in accumulated_parts if p.function_call is not None]
        if not function_calls:
            return

        # Gemini can request several independent tools in one turn — run
        # them concurrently rather than one round trip at a time.
        outcomes = await asyncio.gather(
            *(_call_mcp_tool(org_id, fc.name, dict(fc.args or {})) for fc in function_calls),
            return_exceptions=True,
        )

        response_parts = []
        for fc, outcome in zip(function_calls, outcomes):
            if isinstance(outcome, BaseException):
                logger.exception(
                    "MCP tool call failed mid-stream: %s", fc.name, exc_info=outcome
                )
                yield sse("error", {"error": "MCP server unavailable"})
                return
            result_text, is_error = outcome
            yield sse(
                "tool_call",
                {
                    "tool": fc.name,
                    "input": dict(fc.args or {}),
                    "result": result_text,
                    "is_error": is_error,
                },
            )
            response_parts.append(
                types.Part.from_function_response(
                    name=fc.name,
                    response={"result": result_text, "is_error": is_error},
                )
            )
        current_contents.append(types.Content(role="user", parts=response_parts))

    yield sse(
        "error",
        {"error": "Tool-call loop exceeded maximum iterations without a final answer"},
    )
