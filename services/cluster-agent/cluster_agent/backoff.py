"""Exponential backoff on connectivity loss (E22-T3-S10).

Doubles the delay after each connectivity failure, capped at
BACKOFF_MAX_SECONDS, and resets to BACKOFF_INITIAL_SECONDS after any
success — a transient blip degrades gracefully, a healthy connection
recovers to full speed immediately.
"""

from __future__ import annotations

from .config import BACKOFF_INITIAL_SECONDS, BACKOFF_MAX_SECONDS


class Backoff:
    def __init__(self, initial: float = BACKOFF_INITIAL_SECONDS, maximum: float = BACKOFF_MAX_SECONDS) -> None:
        self._initial = initial
        self._max = maximum
        self._current = initial

    def reset(self) -> None:
        self._current = self._initial

    def next_delay(self) -> float:
        delay = self._current
        self._current = min(self._current * 2, self._max)
        return delay
