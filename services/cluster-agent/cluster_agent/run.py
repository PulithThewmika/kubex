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

import httpx

from . import argocd, bootstrap as bootstrap_module, ingest_client, prometheus
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
    argocd_result = await argocd.discover()
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
    cluster's id."""
    identity = await bootstrap_module.verify_identity()
    await _discover()
    return identity["id"]


async def _run_with_backoff(name: str, backoff: Backoff, fn) -> None:
    """Run fn() once; on connectivity failure, sleep the next backoff delay
    instead of propagating. Any other exception is logged and swallowed too
    (matching services/agent's per-iteration isolation) so one bad tick
    never kills the loop."""
    try:
        await fn()
        backoff.reset()
    except _CONNECTIVITY_ERRORS as e:
        delay = backoff.next_delay()
        logger.warning("%s: connectivity error (%s), retrying in %.0fs", name, e, delay)
        await asyncio.sleep(delay)
    except ingest_client.AuthError:
        logger.error("%s: cluster token rejected — check the Secret matches the current token", name)
    except Exception:
        logger.exception("%s: unexpected error", name)


async def _heartbeat_tick() -> None:
    await ingest_client.heartbeat(
        agent_version=AGENT_VERSION,
        argocd_version=_state["argocd_version"],
        argocd_status=_state["argocd_status"],
        prometheus_status=_state["prometheus_status"],
    )


async def heartbeat_loop(cluster_id: str) -> None:
    backoff = Backoff()
    while not _shutdown_event.is_set():
        await _run_with_backoff("heartbeat", backoff, _heartbeat_tick)
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
        await _run_with_backoff("query_relay", backoff, lambda: _query_relay_tick(cluster_id))
        await asyncio.sleep(QUERY_POLL_INTERVAL_SECONDS)


async def argocd_selfheal_loop() -> None:
    """Re-check discovery (ArgoCD + Prometheus) periodically (#671) — picks
    up a fresh install and re-patches the notifications ConfigMap if its
    keys were reverted (e.g. by an ArgoCD self-sync of its own config)."""
    while not _shutdown_event.is_set():
        await asyncio.sleep(ARGOCD_RECHECK_INTERVAL_SECONDS)
        if _shutdown_event.is_set():
            break
        try:
            await _discover()
        except Exception:
            logger.exception("argocd_selfheal: discovery failed")


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
