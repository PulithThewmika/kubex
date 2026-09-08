"""HTTP client for the ingest service's remote-cluster API (EPIC-022 / E22-T1).

Talks bearer-token auth against POST /api/clusters/verify, POST
/api/clusters/heartbeat, GET /api/clusters/:id/queries and POST
/api/clusters/:id/results — see services/ingest/app/routers/clusters.py
(verify_cluster_token) for the server side of every call here.
"""

from __future__ import annotations

import logging

import httpx

from .config import CLUSTER_TOKEN, DEPLOYLENS_ENDPOINT

logger = logging.getLogger("kubex.cluster_agent.ingest_client")


class AuthError(Exception):
    """The cluster token was rejected (401) — not retryable, needs a human."""


_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            base_url=DEPLOYLENS_ENDPOINT,
            headers={"Authorization": f"Bearer {CLUSTER_TOKEN}"},
            timeout=10.0,
        )
    return _client


async def close_client() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


def _raise_for_status(resp: httpx.Response) -> None:
    if resp.status_code == 401:
        raise AuthError(f"Cluster token rejected by {resp.request.url}")
    resp.raise_for_status()


async def verify() -> dict:
    resp = await get_client().post("/api/clusters/verify")
    _raise_for_status(resp)
    return resp.json()


async def heartbeat(
    *,
    agent_version: str | None,
    argocd_version: str | None,
    argocd_status: str | None,
    prometheus_status: str | None,
    prometheus_namespace: str | None = None,
    prometheus_service: str | None = None,
) -> dict:
    body = {
        "agent_version": agent_version,
        "argocd_version": argocd_version,
        "argocd_status": argocd_status,
        "prometheus_status": prometheus_status,
        "prometheus_namespace": prometheus_namespace,
        "prometheus_service": prometheus_service,
    }
    resp = await get_client().post("/api/clusters/heartbeat", json=body)
    _raise_for_status(resp)
    return resp.json()


async def list_queries(cluster_id: str) -> list[dict]:
    resp = await get_client().get(f"/api/clusters/{cluster_id}/queries")
    _raise_for_status(resp)
    return resp.json()


async def submit_result(cluster_id: str, query_id: str, result: dict) -> None:
    resp = await get_client().post(
        f"/api/clusters/{cluster_id}/results",
        json={"query_id": query_id, "result": result},
    )
    _raise_for_status(resp)
