"""Cluster agent entry point (EPIC-022 / E22-T3).

Boots, validates the cluster token, discovers ArgoCD and Prometheus, then
runs three concurrent loops for the life of the process:
  - heartbeat: POST /api/clusters/heartbeat every HEARTBEAT_INTERVAL_SECONDS
  - query relay: poll GET /api/clusters/:id/queries, execute PromQL, push
    results, every QUERY_POLL_INTERVAL_SECONDS
  - ArgoCD self-heal: re-check/re-patch the notifications ConfigMap every
    ARGOCD_RECHECK_INTERVAL_SECONDS (#671) — also refreshes discovery state
    so a Prometheus/ArgoCD install that appears after boot gets picked up

Each loop backs off exponentially (cluster_agent.backoff) on connectivity
loss to DEPLOYLENS_ENDPOINT and resets on the next success, so a network
blip doesn't spin the agent into a hot retry loop.
"""

from __future__ import annotations

import asyncio
import logging
import signal
from datetime import datetime, timezone
from typing import Awaitable, Callable

import httpx

from . import argocd, bootstrap as bootstrap_module, event_buffer, ingest_client, prometheus
from .backoff import Backoff
from .config import (
    AGENT_VERSION,
    ARGOCD_RECHECK_INTERVAL_SECONDS,
    HEARTBEAT_INTERVAL_SECONDS,
    QUERY_POLL_INTERVAL_SECONDS,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("kubex.cluster_agent")

_shutdown_event = asyncio.Event()

# Discovery state shared across loops. Written only by _discover(); read by
# the heartbeat loop. A plain dict is enough — everything here runs on one
# asyncio event loop, so there's no concurrent-write race to guard against.
_state: dict = {
    "argocd_status": None,
    "argocd_version": None,
    "argocd_namespace": None,
    "prometheus_status": None,
    "prometheus_namespace": None,
    "prometheus_service": None,
}

_CONNECTIVITY_ERRORS = (httpx.TransportError, httpx.TimeoutException)


async def _discover() -> None:
    previous_argocd_status = _state["argocd_status"]
    argocd_result = await argocd.discover()
    if previous_argocd_status is not None and argocd_result["status"] != previous_argocd_status:
        # heartbeat_loop only ever reports the *current* status, so a
        # transition that happens while heartbeat can't reach ingest would
        # otherwise be lost the moment a later transition overwrites it —
        # buffer it here so it survives to the next successful heartbeat.
        event_buffer.push({
            "from_status": previous_argocd_status,
            "to_status": argocd_result["status"],
            "version": argocd_result["version"],
            "namespace": argocd_result["namespace"],
            "detected_at": datetime.now(timezone.utc).isoformat(),
        })
    _state["argocd_status"] = argocd_result["status"]
    _state["argocd_version"] = argocd_result["version"]
    _state["argocd_namespace"] = argocd_result["namespace"]

    prom_result = await prometheus.discover()
    _state["prometheus_status"] = prom_result["status"]
    _state["prometheus_namespace"] = prom_result["namespace"]
    _state["prometheus_service"] = prom_result["service_name"]

    logger.info(
        "Discovery: argocd=%s (version=%s) prometheus=%s",
        _state["argocd_status"], _state["argocd_version"], _state["prometheus_status"],
    )


async def bootstrap() -> str:
    """Validate the cluster token, run initial discovery, return this
    cluster's id. Retries indefinitely (with backoff) on a connectivity
    failure reaching DEPLOYLENS_ENDPOINT — bug found in review, E22-T3:
    this previously had no retry at all, so the agent crashed if the
    ingest endpoint wasn't reachable yet at Pod startup (a rolling
    restart, DNS not yet resolvable), unlike every other network call in
    this module. Config errors (RuntimeError from config.validate()) and
    a rejected token (AuthError) still fail fast — retrying either just
    delays a fix a human needs to make."""
    backoff = Backoff()
    while True:
        try:
            identity = await bootstrap_module.verify_identity()
            break
        except _CONNECTIVITY_ERRORS as e:
            delay = backoff.next_delay()
            logger.warning("bootstrap: connectivity error (%s), retrying in %.0fs", e, delay)
            await asyncio.sleep(delay)
    await _discover()
    return identity["id"]


async def _run_with_backoff(name: str, backoff: Backoff, fn: Callable[[], Awaitable[None]]) -> bool:
    """Run fn() once. Returns True if this call already slept a delay
    itself (a connectivity backoff, or a fatal AuthError shutting the
    agent down) — the caller should skip its own normal interval sleep in
    that case rather than stacking both delays (bug found in review,
    E22-T3: heartbeat_loop/query_relay_loop previously always slept the
    fixed interval on top of any backoff delay already slept here, so a
    connectivity failure's retry cadence was backoff+interval instead of
    just backoff, the opposite of the intended "backs off, then resets on
    success" behavior)."""
    try:
        await fn()
        backoff.reset()
        return False
    except _CONNECTIVITY_ERRORS as e:
        delay = backoff.next_delay()
        logger.warning("%s: connectivity error (%s), retrying in %.0fs", name, e, delay)
        await asyncio.sleep(delay)
        return True
    except ingest_client.AuthError:
        # Not retryable — a rejected token stays rejected until a human
        # fixes it. Shut the agent down (bug found in review, E22-T3: this
        # previously just logged and let every loop keep retrying the same
        # rejected token every interval forever) so the Pod restarts and
        # picks up a corrected Secret rather than spinning uselessly.
        logger.error("%s: cluster token rejected — shutting down (check the Secret matches the current token)", name)
        _shutdown_event.set()
        return True
    except Exception:
        logger.exception("%s: unexpected error", name)
        return False


async def _heartbeat_tick() -> None:
    await ingest_client.heartbeat(
        agent_version=AGENT_VERSION,
        argocd_version=_state["argocd_version"],
        argocd_status=_state["argocd_status"],
        prometheus_status=_state["prometheus_status"],
    )
    if event_buffer.size():
        # Reaching here means the heartbeat POST above just succeeded, so
        # any buffered transitions are safe to report and drop. Not
        # necessarily from an outage, though: argocd_selfheal_loop runs on
        # its own schedule independent of heartbeat's, so a transition can
        # land in the buffer moments before a heartbeat that was going to
        # succeed anyway — don't assert a connectivity outage occurred,
        # just report what transitioned. Nothing to send them to besides
        # this log (ingest's heartbeat endpoint carries current state only,
        # not history).
        buffered = event_buffer.drain()
        logger.warning(
            "Reporting %d buffered ArgoCD status transition(s): %s",
            len(buffered), buffered,
        )


async def heartbeat_loop(cluster_id: str) -> None:
    backoff = Backoff()
    while not _shutdown_event.is_set():
        already_waited = await _run_with_backoff("heartbeat", backoff, _heartbeat_tick)
        if not already_waited:
            await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)


async def _query_relay_tick(cluster_id: str) -> None:
    queries = await ingest_client.list_queries(cluster_id)
    if not queries:
        return
    if _state["prometheus_status"] != "found":
        logger.warning("Skipping %d pending quer(y/ies): Prometheus not discovered", len(queries))
        return
    base_url = prometheus.in_cluster_url(_state["prometheus_namespace"], _state["prometheus_service"])
    for q in queries:
        try:
            result = await prometheus.query(base_url, q["promql"])
        except Exception:
            logger.exception("Failed to execute PromQL for query %s", q["id"])
            continue
        await ingest_client.submit_result(cluster_id, q["id"], result)


async def query_relay_loop(cluster_id: str) -> None:
    backoff = Backoff()
    while not _shutdown_event.is_set():
        already_waited = await _run_with_backoff("query_relay", backoff, lambda: _query_relay_tick(cluster_id))
        if not already_waited:
            await asyncio.sleep(QUERY_POLL_INTERVAL_SECONDS)


async def argocd_selfheal_loop() -> None:
    """Re-check discovery (ArgoCD + Prometheus) periodically (#671) — picks
    up a fresh install and re-patches the notifications ConfigMap if its
    keys were reverted (e.g. by an ArgoCD self-sync of its own config).
    Routed through _run_with_backoff like the other two loops (bug found
    in review, E22-T3: this previously had its own bespoke try/except with
    no backoff, inconsistent with the rest of the module)."""
    backoff = Backoff()
    while not _shutdown_event.is_set():
        already_waited = await _run_with_backoff("argocd_selfheal", backoff, _discover)
        if not already_waited:
            await asyncio.sleep(ARGOCD_RECHECK_INTERVAL_SECONDS)


async def shutdown() -> None:
    logger.info("Shutting down cluster agent...")
    _shutdown_event.set()
    await ingest_client.close_client()
    await prometheus.close_client()


async def main() -> None:
    logger.info("KubeX cluster agent starting (version %s)", AGENT_VERSION)
    cluster_id = await bootstrap()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: _shutdown_event.set())
        except NotImplementedError:
            signal.signal(sig, lambda s, f: _shutdown_event.set())

    tasks = [
        asyncio.create_task(heartbeat_loop(cluster_id)),
        asyncio.create_task(query_relay_loop(cluster_id)),
        asyncio.create_task(argocd_selfheal_loop()),
    ]

    logger.info("Agent running — waiting for shutdown signal")
    await _shutdown_event.wait()
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
