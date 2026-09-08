import logging
import os
import re
from collections.abc import AsyncIterator
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth_middleware import UserContext, get_current_user
from ..db import get_session
from ..models.cluster import Cluster
from ..models.service import Service

logger = logging.getLogger("kubex.ingest.grafana")

router = APIRouter(prefix="/api/grafana", tags=["grafana"])

GRAFANA_URL = os.environ.get("GRAFANA_URL", "http://grafana:3000")
GRAFANA_SERVICE_ACCOUNT_TOKEN = os.environ.get("GRAFANA_SERVICE_ACCOUNT_TOKEN", "")

# Only these dashboard uids may be embedded through this proxy. `uid` comes
# from the browser; without an allow-list a caller could name any dashboard
# in the Grafana org (operator-only ones included) and read it. These are
# the org-scoped-by-construction customer set (deploy/grafana/dashboards/
# customer/ — every SQL panel filters org_id/'$org', #834).
EMBEDDABLE_DASHBOARD_UIDS = {"deploy-timeline", "customer-dora-scorecard"}

_RE2_META = re.compile(r"([\\.+*?()|\[\]{}^$])")


def _re2_quote(value: str) -> str:
    """Escape a Prometheus label value so it matches literally inside the
    panel's ``service=~"$service"`` matcher (RE2). ``prom_components`` is
    free-text ``ARRAY(Text)``; a value like ``api.v1`` or one containing
    ``|`` would otherwise widen the selector."""
    return _RE2_META.sub(r"\\\1", value)


_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        # Generous: a PNG render drives a datasource query that itself
        # blocks on the cluster-agent relay (#832, ~20s worst case) before
        # headless Chrome paints.
        _client = httpx.AsyncClient(base_url=GRAFANA_URL, timeout=45.0)
    return _client


@router.get("/proxy")
async def grafana_proxy(
    uid: str,
    panelId: int,
    service: str = Query(alias="var-service"),
    from_: str = Query(default="now-6h", alias="from"),
    to: str = Query(default="now"),
    theme: str = Query(default="light"),
    width: int = Query(default=1000, ge=100, le=3000),
    height: int = Query(default=300, ge=100, le=2000),
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Render an embedded Grafana panel to PNG for the React shell.

    Tenant isolation is enforced here, server-side — the browser is not
    trusted (CLAUDE.md decision 9):

    * ``uid`` must name a known embeddable dashboard.
    * ``var-service`` must name a service owned by the caller's org; it is
      resolved to that service's ``prom_components`` (a KubeX service can
      roll up several Prometheus components — see the architecture gotcha)
      before being forwarded as the panel's ``$service`` matcher.
    * ``var-org`` is injected from ``UserContext``; any client-supplied
      value is ignored. The customer-facing dashboard's SQL panels
      constrain ``org_id = '$org'`` (deploy-timeline.json), so the
      deployment-metadata panels are tenant-isolated here and now. The
      Prometheus metric panels (error rate / latency / restarts) get
      their tenant boundary from the datasource relay instead — until
      #832 repoints ``kubex-prometheus`` at the org-scoped relay they
      still read the operator-local Prometheus.

    The Grafana service account token is injected server-side and never
    reaches the browser.

    Uses Grafana's ``/render/d-solo/`` (grafana-image-renderer, #835) and
    returns the PNG. The earlier ``/d-solo/`` HTML never rendered from
    this proxy's origin — its JS/CSS/API are relative to ``/`` and 404
    (E11-T2). A PNG has no such dependency.
    """
    if uid not in EMBEDDABLE_DASHBOARD_UIDS:
        raise HTTPException(status_code=404, detail="Unknown dashboard")

    row = (
        await session.execute(
            select(Service.prom_components).where(
                Service.name == service, Service.org_id == user.org_id
            )
        )
    ).first()
    if row is None:
        # 404, not 403: don't confirm the service exists in another org.
        raise HTTPException(status_code=404, detail="Unknown service")
    components = row[0] or [service]

    has_source = await session.scalar(
        select(Cluster.id)
        .where(Cluster.org_id == user.org_id, Cluster.status == "connected")
        .limit(1)
    )
    if has_source is None:
        raise HTTPException(status_code=503, detail="no metrics source connected")

    params = {
        "panelId": panelId,
        # Prometheus panels match service=~"$service" (RE2, auto-anchored);
        # each component is escaped so it's a literal alternative.
        "var-service": "|".join(_re2_quote(c) for c in components),
        "var-org": str(user.org_id),
        "from": from_,
        "to": to,
        "theme": theme,
        "width": width,
        "height": height,
    }
    headers = {"Authorization": f"Bearer {GRAFANA_SERVICE_ACCOUNT_TOKEN}"}

    client = _get_client()
    try:
        # uid is escaped before it's spliced into the path — otherwise a
        # uid containing "?"/"&" could inject extra query parameters
        # ahead of the ones set above.
        request = client.build_request(
            "GET", f"/render/d-solo/{quote(uid, safe='')}", params=params, headers=headers
        )
        upstream = await client.send(request, stream=True)
    except httpx.RequestError:
        logger.exception("Grafana unreachable at %s", GRAFANA_URL)
        raise HTTPException(status_code=502, detail="Grafana unreachable")

    async def body() -> AsyncIterator[bytes]:
        try:
            async for chunk in upstream.aiter_bytes():
                yield chunk
        finally:
            await upstream.aclose()

    # Allow-list rather than strip: only content-type is safe/meaningful
    # to forward. This also sidesteps re-sending upstream's
    # content-encoding/content-length, which would mismatch the
    # re-chunked body we're streaming here.
    response_headers = {}
    if "content-type" in upstream.headers:
        response_headers["content-type"] = upstream.headers["content-type"]

    return StreamingResponse(
        body(),
        status_code=upstream.status_code,
        headers=response_headers,
    )
