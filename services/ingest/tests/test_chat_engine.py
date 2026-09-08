"""Tests for the chat engine's SSE framing and tool-use loop."""

import os
import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.genai import errors as genai_errors
from google.genai import types

os.environ.setdefault("GEMINI_API_KEY", "test-key")

from app.chat_engine import run_chat_turn  # noqa: E402
from app.schemas.chat import ChatMessage  # noqa: E402

TEST_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


def _text_part(text):
    # A real types.Part, not a MagicMock — chat_engine.py builds a real
    # types.Content(parts=...) from these, which pydantic-validates every
    # part; a loosely-mocked part fails that validation with cryptic
    # field-coercion errors instead of a clean assertion failure.
    return types.Part.from_text(text=text)


def _function_call_part(id_, name, args):
    return types.Part(function_call=types.FunctionCall(name=name, args=args))


def _api_error(code, status="UNAVAILABLE"):
    error_cls = genai_errors.ServerError if code >= 500 else genai_errors.ClientError
    return error_cls(code, {"error": {"code": code, "message": "busy", "status": status}})


def _chunk(text, parts):
    chunk = MagicMock()
    chunk.text = text
    candidate = MagicMock()
    candidate.content.parts = parts
    chunk.candidates = [candidate]
    return chunk


class _FakeStream:
    """Re-iterable async stream — __aiter__ builds a fresh generator each
    time so the same instance can be replayed across tool-loop iterations
    (needed by the max-iterations test)."""

    def __init__(self, chunks):
        self._chunks = chunks

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for chunk in self._chunks:
            yield chunk


@pytest.mark.asyncio
async def test_run_chat_turn_streams_text_only():
    stream = _FakeStream([_chunk("Hello", [_text_part("Hello")]), _chunk(" there", [_text_part(" there")])])

    mock_client = MagicMock()
    mock_client.aio.models.generate_content_stream = AsyncMock(return_value=stream)

    with patch("app.chat_engine.genai.Client", return_value=mock_client):
        frames = [
            frame
            async for frame in run_chat_turn(
                [ChatMessage(role="user", content="hi")], tools=[], org_id=TEST_ORG_ID
            )
        ]

    assert frames == [
        'event: text\ndata: {"text": "Hello"}\n\n',
        'event: text\ndata: {"text": " there"}\n\n',
    ]


@pytest.mark.asyncio
async def test_run_chat_turn_includes_tool_call_results():
    first_stream = _FakeStream([_chunk(None, [_function_call_part("tool_1", "list_deployments", {"service": "orders"})])])
    second_stream = _FakeStream([_chunk("done", [_text_part("done")])])

    mock_client = MagicMock()
    mock_client.aio.models.generate_content_stream = AsyncMock(side_effect=[first_stream, second_stream])

    mock_mcp_session = AsyncMock()
    mock_mcp_session.call_tool.return_value = MagicMock(
        content=[MagicMock(text='{"deployments": []}')],
        is_error=False,
    )
    received_org_ids = []

    @asynccontextmanager
    async def fake_mcp_session(org_id):
        received_org_ids.append(org_id)
        yield mock_mcp_session

    with (
        patch("app.chat_engine.genai.Client", return_value=mock_client),
        patch("app.chat_engine.mcp_session", fake_mcp_session),
    ):
        frames = [
            frame
            async for frame in run_chat_turn(
                [ChatMessage(role="user", content="list deploys")], tools=[], org_id=TEST_ORG_ID
            )
        ]

    assert any(f.startswith("event: tool_call\n") for f in frames)
    tool_call_frame = next(f for f in frames if f.startswith("event: tool_call\n"))
    assert '"tool": "list_deployments"' in tool_call_frame
    assert '"result": "{\\"deployments\\": []}"' in tool_call_frame
    assert frames[-1] == 'event: text\ndata: {"text": "done"}\n\n'
    assert received_org_ids == [TEST_ORG_ID]
    mock_mcp_session.call_tool.assert_awaited_once_with(
        "list_deployments", {"service": "orders"}
    )


@pytest.mark.asyncio
async def test_run_chat_turn_runs_parallel_tool_calls_concurrently():
    import asyncio
    import time

    first_stream = _FakeStream([
        _chunk(None, [
            _function_call_part("tool_a", "get_dora_metrics", {}),
            _function_call_part("tool_b", "get_active_alerts", {}),
        ])
    ])
    second_stream = _FakeStream([_chunk("done", [_text_part("done")])])

    mock_client = MagicMock()
    mock_client.aio.models.generate_content_stream = AsyncMock(side_effect=[first_stream, second_stream])

    call_started_at: list[float] = []

    async def slow_call_tool(name, arguments):
        call_started_at.append(time.monotonic())
        await asyncio.sleep(0.05)
        return MagicMock(content=[MagicMock(text="{}")], is_error=False)

    mock_mcp_session = AsyncMock()
    mock_mcp_session.call_tool.side_effect = slow_call_tool

    @asynccontextmanager
    async def fake_mcp_session(org_id):
        yield mock_mcp_session

    with (
        patch("app.chat_engine.genai.Client", return_value=mock_client),
        patch("app.chat_engine.mcp_session", fake_mcp_session),
    ):
        start = time.monotonic()
        frames = [
            frame
            async for frame in run_chat_turn(
                [ChatMessage(role="user", content="give me an overview")], tools=[], org_id=TEST_ORG_ID
            )
        ]
        elapsed = time.monotonic() - start

    tool_call_frames = [f for f in frames if f.startswith("event: tool_call\n")]
    assert len(tool_call_frames) == 2
    # Two 50ms calls run concurrently should take well under 100ms total.
    assert elapsed < 0.09
    assert len(call_started_at) == 2
    assert abs(call_started_at[0] - call_started_at[1]) < 0.02


@pytest.mark.asyncio
async def test_run_chat_turn_stops_after_max_iterations():
    stream = _FakeStream([_chunk(None, [_function_call_part("tool_1", "list_deployments", {})])])

    mock_client = MagicMock()
    mock_client.aio.models.generate_content_stream = AsyncMock(return_value=stream)

    mock_mcp_session = AsyncMock()
    mock_mcp_session.call_tool.return_value = MagicMock(
        content=[MagicMock(text="{}")], is_error=False
    )

    @asynccontextmanager
    async def fake_mcp_session(org_id):
        yield mock_mcp_session

    with (
        patch("app.chat_engine.genai.Client", return_value=mock_client),
        patch("app.chat_engine.mcp_session", fake_mcp_session),
    ):
        frames = [
            frame
            async for frame in run_chat_turn(
                [ChatMessage(role="user", content="loop forever")], tools=[], org_id=TEST_ORG_ID
            )
        ]

    assert frames[-1].startswith("event: error\n")
    assert "maximum iterations" in frames[-1]


# ── retry-with-backoff on transient Gemini errors ────────────────────

@pytest.mark.asyncio
async def test_run_chat_turn_retries_transient_503_then_succeeds():
    success_stream = _FakeStream([_chunk("ok", [_text_part("ok")])])

    mock_client = MagicMock()
    mock_client.aio.models.generate_content_stream = AsyncMock(
        side_effect=[_api_error(503), _api_error(503), success_stream]
    )

    with (
        patch("app.chat_engine.genai.Client", return_value=mock_client),
        patch("app.chat_engine.asyncio.sleep", AsyncMock()),
    ):
        frames = [
            frame
            async for frame in run_chat_turn(
                [ChatMessage(role="user", content="hi")], tools=[], org_id=TEST_ORG_ID
            )
        ]

    assert frames == ['event: text\ndata: {"text": "ok"}\n\n']
    assert mock_client.aio.models.generate_content_stream.await_count == 3


@pytest.mark.asyncio
async def test_run_chat_turn_does_not_retry_non_retryable_error():
    mock_client = MagicMock()
    mock_client.aio.models.generate_content_stream = AsyncMock(
        side_effect=_api_error(400, status="INVALID_ARGUMENT")
    )

    with (
        patch("app.chat_engine.genai.Client", return_value=mock_client),
        patch("app.chat_engine.asyncio.sleep", AsyncMock()) as mock_sleep,
    ):
        frames = [
            frame
            async for frame in run_chat_turn(
                [ChatMessage(role="user", content="hi")], tools=[], org_id=TEST_ORG_ID
            )
        ]

    assert frames[-1].startswith("event: error\n")
    assert mock_client.aio.models.generate_content_stream.await_count == 1
    mock_sleep.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_chat_turn_gives_up_after_max_retries():
    mock_client = MagicMock()
    mock_client.aio.models.generate_content_stream = AsyncMock(side_effect=_api_error(503))

    with (
        patch("app.chat_engine.genai.Client", return_value=mock_client),
        patch("app.chat_engine.asyncio.sleep", AsyncMock()),
    ):
        frames = [
            frame
            async for frame in run_chat_turn(
                [ChatMessage(role="user", content="hi")], tools=[], org_id=TEST_ORG_ID
            )
        ]

    assert frames[-1].startswith("event: error\n")
    assert "LLM service unavailable" in frames[-1]
    # _MAX_RETRIES=2 -> 3 total attempts
    assert mock_client.aio.models.generate_content_stream.await_count == 3


@pytest.mark.asyncio
async def test_run_chat_turn_does_not_retry_after_partial_output_sent():
    """A failure after some text has already reached the client must not
    retry — the response already has partial content committed, and
    retrying would duplicate rather than replace it."""

    class _FailingStream:
        def __aiter__(self):
            return self._gen()

        async def _gen(self):
            yield _chunk("partial", [_text_part("partial")])
            raise _api_error(503)

    mock_client = MagicMock()
    mock_client.aio.models.generate_content_stream = AsyncMock(return_value=_FailingStream())

    with (
        patch("app.chat_engine.genai.Client", return_value=mock_client),
        patch("app.chat_engine.asyncio.sleep", AsyncMock()) as mock_sleep,
    ):
        frames = [
            frame
            async for frame in run_chat_turn(
                [ChatMessage(role="user", content="hi")], tools=[], org_id=TEST_ORG_ID
            )
        ]

    assert frames[0] == 'event: text\ndata: {"text": "partial"}\n\n'
    assert frames[-1].startswith("event: error\n")
    mock_sleep.assert_not_awaited()
    assert mock_client.aio.models.generate_content_stream.await_count == 1
