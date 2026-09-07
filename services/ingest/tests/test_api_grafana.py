"""Tests for GET /api/grafana/proxy (tenant-scoped panel proxy, #833)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from httpx import ASGITransport, AsyncClient


def _mock_upstream(status_code: int = 200, content_type: str = "text/html; charset=UTF-8", chunks: object = None) -> MagicMock:
    chunks = chunks or [b"<html>panel</html>"]
    upstream = MagicMock()
    upstream.status_code = status_code
    upstream.headers = {"content-type": content_type} if content_type else {}
    upstream.aclose = AsyncMock()

    async def aiter_bytes():
        for chunk in chunks:
            yield chunk

    upstream.aiter_bytes = aiter_bytes
    return upstream


def _stub_session(
    mock_session: object, *, prom_components: object = ("orders",), has_source: bool = True
) -> None:
    """Wire mock_session so the proxy's service lookup and connected-cluster
    check resolve. prom_components=None -> service row exists with no
    components; prom_components=False -> no matching service row (cross-org
    or unknown)."""
    mock_session.execute.side_effect = None
    row = None if prom_components is False else (list(prom_components) if prom_components else None,)
    mock_session.execute.return_value = MagicMock(first=MagicMock(return_value=row))
    mock_session.scalar = AsyncMock(return_value=uuid.uuid4() if has_source else None)


def _mock_grafana_client() -> MagicMock:
    upstream = _mock_upstream(chunks=[b"<html>", b"panel", b"</html>"])
    c = MagicMock()
    c.build_request = MagicMock(return_value="fake-request")
    c.send = AsyncMock(return_value=upstream)
    return c


@pytest.mark.asyncio
async def test_proxy_returns_grafana_panel_html(client, mock_session) -> None:
    _stub_session(mock_session)
    grafana_client = _mock_grafana_client()

    with (
        patch("app.routers.grafana.GRAFANA_SERVICE_ACCOUNT_TOKEN", "super-secret-token"),
        patch("app.routers.grafana._get_client", return_value=grafana_client),
    ):
        async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
            resp = await ac.get(
                "/api/grafana/proxy",
                params={"uid": "deploy-timeline", "panelId": 1, "var-service": "orders"},
            )

    assert resp.status_code == 200
    assert resp.text == "<html>panel</html>"

    sent = grafana_client.build_request.call_args
    assert sent.kwargs["headers"]["Authorization"] == "Bearer super-secret-token"
    # The SA token is forwarded to Grafana, never echoed to the browser.
    assert "super-secret-token" not in resp.text
    assert "authorization" not in {h.lower() for h in resp.headers}
    assert resp.headers["content-type"] == "text/html; charset=UTF-8"
    # org is injected server-side from UserContext, service is resolved.
    assert sent.kwargs["params"]["var-org"] == "00000000-0000-0000-0000-000000000002"
    assert sent.kwargs["params"]["var-service"] == "orders"


@pytest.mark.asyncio
async def test_proxy_expands_prom_components(client, mock_session) -> None:
    _stub_session(mock_session, prom_components=("frontend", "orders", "payments"))
    grafana_client = _mock_grafana_client()

    with patch("app.routers.grafana._get_client", return_value=grafana_client):
        async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
            resp = await ac.get(
                "/api/grafana/proxy",
                params={"uid": "deploy-timeline", "panelId": 1, "var-service": "sample-app"},
            )

    assert resp.status_code == 200
    assert grafana_client.build_request.call_args.kwargs["params"]["var-service"] == (
        "frontend|orders|payments"
    )


@pytest.mark.asyncio
async def test_proxy_rejects_unknown_dashboard_uid(client, mock_session) -> None:
    _stub_session(mock_session)
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get(
            "/api/grafana/proxy",
            params={"uid": "platform-overview", "panelId": 1, "var-service": "orders"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_proxy_rejects_service_from_another_org(client, mock_session) -> None:
    # No service row for (name, this org) -> cross-tenant read attempt.
    _stub_session(mock_session, prom_components=False)
    grafana_client = _mock_grafana_client()

    with patch("app.routers.grafana._get_client", return_value=grafana_client):
        async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
            resp = await ac.get(
                "/api/grafana/proxy",
                params={"uid": "deploy-timeline", "panelId": 1, "var-service": "org-b-service"},
            )

    assert resp.status_code == 404
    grafana_client.send.assert_not_called()


@pytest.mark.asyncio
async def test_proxy_requires_var_service(client, mock_session) -> None:
    _stub_session(mock_session)
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/api/grafana/proxy", params={"uid": "deploy-timeline", "panelId": 1})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_proxy_503_when_no_connected_cluster(client, mock_session) -> None:
    _stub_session(mock_session, has_source=False)
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get(
            "/api/grafana/proxy",
            params={"uid": "deploy-timeline", "panelId": 1, "var-service": "orders"},
        )
    assert resp.status_code == 503
    assert resp.json()["detail"] == "no metrics source connected"


@pytest.mark.asyncio
async def test_proxy_escapes_uid_before_building_url(client, mock_session) -> None:
    # A tampered uid still has to pass the allow-list first.
    _stub_session(mock_session)
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get(
            "/api/grafana/proxy",
            params={
                "uid": "deploy-timeline?var-service=.*",
                "panelId": 1,
                "var-service": "orders",
            },
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_proxy_returns_502_when_grafana_unreachable(client, mock_session) -> None:
    _stub_session(mock_session)
    grafana_client = MagicMock()
    grafana_client.build_request = MagicMock(return_value="fake-request")
    grafana_client.send = AsyncMock(side_effect=httpx.ConnectError("connection refused"))

    with patch("app.routers.grafana._get_client", return_value=grafana_client):
        async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
            resp = await ac.get(
                "/api/grafana/proxy",
                params={"uid": "deploy-timeline", "panelId": 1, "var-service": "orders"},
            )

    assert resp.status_code == 502
    assert resp.json()["detail"] == "Grafana unreachable"
