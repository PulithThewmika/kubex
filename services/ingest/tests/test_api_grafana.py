"""Tests for GET /api/grafana/proxy (tenant-scoped panel proxy, #833/#835)."""

import contextlib
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


def _mock_upstream(status_code: int = 200, content_type: str = "image/png", chunks: object = None) -> MagicMock:
    chunks = chunks or [b"PNG-bytes"]
    upstream = MagicMock()
    upstream.status_code = status_code
    upstream.headers = {"content-type": content_type} if content_type else {}
    upstream.aclose = AsyncMock()

    async def aiter_bytes():
        for chunk in chunks:
            yield chunk

    upstream.aiter_bytes = aiter_bytes
    return upstream


class _FakeSession:
    def __init__(self, *, service_row, scalars):
        self._service_row = service_row
        self._scalars = list(scalars)
        self.commit = AsyncMock()

    async def execute(self, *_a, **_k):
        result = MagicMock()
        result.first = MagicMock(return_value=self._service_row)
        return result

    async def scalar(self, *_a, **_k):
        return self._scalars.pop(0) if self._scalars else None


def _patch_session(*, prom_components=("orders",), has_source=True, owns_cluster=True):
    """prom_components=False -> no service row (cross-org / unknown)."""
    service_row = None if prom_components is False else (list(prom_components) if prom_components else None,)
    scalars = [uuid.uuid4() if has_source else None]
    scalars.append(uuid.uuid4() if owns_cluster else None)
    session = _FakeSession(service_row=service_row, scalars=scalars)

    @contextlib.asynccontextmanager
    async def factory():
        yield session

    return patch("app.routers.grafana.async_session", factory)


def _mock_grafana_client() -> MagicMock:
    c = MagicMock()
    c.build_request = MagicMock(return_value="fake-request")
    c.send = AsyncMock(return_value=_mock_upstream(chunks=[b"PNG", b"-", b"bytes"]))
    return c


async def _get(**params):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        return await ac.get("/api/grafana/proxy", params=params)


@pytest.mark.asyncio
async def test_proxy_renders_panel_png(client) -> None:
    grafana_client = _mock_grafana_client()
    with (
        _patch_session(),
        patch("app.routers.grafana.GRAFANA_SERVICE_ACCOUNT_TOKEN", "super-secret-token"),
        patch("app.routers.grafana._get_client", return_value=grafana_client),
    ):
        resp = await _get(uid="deploy-timeline", panelId=1, **{"var-service": "orders"})

    assert resp.status_code == 200
    assert resp.content == b"PNG-bytes"

    sent = grafana_client.build_request.call_args
    assert sent.args[1] == "/render/d-solo/deploy-timeline"
    assert sent.kwargs["params"]["width"] == 1000
    assert sent.kwargs["params"]["height"] == 300
    assert sent.kwargs["headers"]["Authorization"] == "Bearer super-secret-token"
    assert b"super-secret-token" not in resp.content
    assert "authorization" not in {h.lower() for h in resp.headers}
    assert sent.kwargs["params"]["var-org"] == "00000000-0000-0000-0000-000000000002"
    assert sent.kwargs["params"]["var-service"] == "orders"
    assert sent.kwargs["params"]["var-component"] == "orders"


@pytest.mark.asyncio
async def test_proxy_expands_prom_components(client) -> None:
    grafana_client = _mock_grafana_client()
    with (
        _patch_session(prom_components=("frontend", "orders", "payments")),
        patch("app.routers.grafana._get_client", return_value=grafana_client),
    ):
        resp = await _get(uid="deploy-timeline", panelId=1, **{"var-service": "sample-app"})

    assert resp.status_code == 200
    params = grafana_client.build_request.call_args.kwargs["params"]
    # SQL panels get the logical name; Prometheus panels get the components.
    assert params["var-service"] == "sample-app"
    assert params["var-component"] == "frontend|orders|payments"


@pytest.mark.asyncio
async def test_proxy_escapes_regex_metacharacters_in_components(client) -> None:
    grafana_client = _mock_grafana_client()
    with (
        _patch_session(prom_components=("api.v1", "foo|bar")),
        patch("app.routers.grafana._get_client", return_value=grafana_client),
    ):
        resp = await _get(uid="deploy-timeline", panelId=1, **{"var-service": "svc"})

    assert resp.status_code == 200
    # `.` and `|` escaped so each stays a literal alternative in service=~"$component"
    assert grafana_client.build_request.call_args.kwargs["params"]["var-component"] == (
        r"api\.v1|foo\|bar"
    )


@pytest.mark.asyncio
async def test_proxy_rejects_control_char_in_component(client) -> None:
    with _patch_session(prom_components=("ok", "bad\nname")):
        resp = await _get(uid="deploy-timeline", panelId=1, **{"var-service": "svc"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_proxy_rejects_unknown_dashboard_uid(client) -> None:
    with _patch_session():
        resp = await _get(uid="platform-overview", panelId=1, **{"var-service": "orders"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_proxy_rejects_service_from_another_org(client) -> None:
    grafana_client = _mock_grafana_client()
    with (
        _patch_session(prom_components=False),
        patch("app.routers.grafana._get_client", return_value=grafana_client),
    ):
        resp = await _get(uid="deploy-timeline", panelId=1, **{"var-service": "org-b-service"})

    assert resp.status_code == 404
    grafana_client.send.assert_not_called()


@pytest.mark.asyncio
async def test_proxy_requires_var_service(client) -> None:
    resp = await _get(uid="deploy-timeline", panelId=1)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_proxy_503_when_no_connected_cluster(client) -> None:
    with _patch_session(has_source=False):
        resp = await _get(uid="deploy-timeline", panelId=1, **{"var-service": "orders"})
    assert resp.status_code == 503
    assert resp.json()["detail"] == "no metrics source connected"


@pytest.mark.asyncio
async def test_proxy_rejects_cluster_from_another_org(client) -> None:
    with _patch_session(owns_cluster=False):
        resp = await _get(
            uid="deploy-timeline",
            panelId=1,
            **{"var-service": "orders", "var-cluster": str(uuid.uuid4())},
        )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Unknown cluster"


@pytest.mark.asyncio
async def test_proxy_tampered_uid_rejected(client) -> None:
    with _patch_session():
        resp = await _get(
            uid="deploy-timeline?var-service=.*", panelId=1, **{"var-service": "orders"}
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_proxy_returns_502_when_grafana_unreachable(client) -> None:
    grafana_client = MagicMock()
    grafana_client.build_request = MagicMock(return_value="fake-request")
    grafana_client.send = AsyncMock(side_effect=httpx.ConnectError("connection refused"))

    with (
        _patch_session(),
        patch("app.routers.grafana._get_client", return_value=grafana_client),
    ):
        resp = await _get(uid="deploy-timeline", panelId=1, **{"var-service": "orders"})

    assert resp.status_code == 502
    assert resp.json()["detail"] == "Grafana unreachable"
