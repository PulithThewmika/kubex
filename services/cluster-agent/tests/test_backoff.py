from __future__ import annotations

from cluster_agent.backoff import Backoff


def test_doubles_and_caps() -> None:
    b = Backoff(initial=1, maximum=8)
    assert b.next_delay() == 1
    assert b.next_delay() == 2
    assert b.next_delay() == 4
    assert b.next_delay() == 8
    assert b.next_delay() == 8  # capped, doesn't keep growing


def test_reset_returns_to_initial() -> None:
    b = Backoff(initial=1, maximum=60)
    b.next_delay()
    b.next_delay()
    b.reset()
    assert b.next_delay() == 1
