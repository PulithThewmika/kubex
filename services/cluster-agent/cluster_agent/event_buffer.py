"""Bounded in-memory buffer for ArgoCD status-change events observed while
connectivity to DEPLOYLENS_ENDPOINT is down (E23-T4-S8).

heartbeat_loop is the only loop that reports ArgoCD status to ingest, so a
status transition detected mid-outage would otherwise be silently
overwritten by the next transition before connectivity returns — ingest
would only ever see the final state, never the intermediate ones. Buffering
each transition here and flushing (logging, then clearing) on the next
successful heartbeat preserves that history for the operator instead.

ponytail: fixed-size deque, oldest event dropped past capacity — these are
transient status snapshots for observability, not an audit trail, so lossy
under an outage exceeding 100 transitions is an acceptable ceiling. Upgrade
to a persistent queue (or push the whole buffer to ingest as a batch) if
that ever proves too small in practice.
"""

from __future__ import annotations

from collections import deque
from typing import Any

_CAPACITY = 100
_buffer: deque[dict[str, Any]] = deque(maxlen=_CAPACITY)


def push(event: dict[str, Any]) -> None:
    _buffer.append(event)


def drain() -> list[dict[str, Any]]:
    events = list(_buffer)
    _buffer.clear()
    return events


def size() -> int:
    return len(_buffer)
