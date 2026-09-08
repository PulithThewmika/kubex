import asyncio
import contextlib
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_fastapi_instrumentator.metrics import Info
from sqlalchemy import text

from . import slack_client
from .auth import validate_auth_tokens
from .cluster_monitor import run_disconnect_sweep_loop
from .crypto import install_log_redaction
from .db import async_session, engine
from .routers import (
    auth,
    webhooks_github,
    webhooks_github_app,
    webhooks_argocd,
    api,
    chat,
    clusters,
    grafana,
    install,
    integrations_slack,
    mcp_connector,
    prom,
    relay_internal,
    settings,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_auth_tokens()
    integrations_slack.validate_slack_config()
    install_log_redaction()
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    sweep_task = asyncio.create_task(run_disconnect_sweep_loop(async_session))
    yield
    sweep_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await sweep_task
    await slack_client.close_client()
    await engine.dispose()


app = FastAPI(
    title="KubeX Ingest",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow React shell origin
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics with required service label (CLAUDE.md Critical Decision #2)
_requests_counter = Counter(
    "kubex_ingest_http_requests_total",
    "Total HTTP requests",
    ["service", "method", "handler", "status"],
)
_duration_histogram = Histogram(
    "kubex_ingest_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["service", "method", "handler", "status"],
)


def _count_requests(info: Info) -> None:
    _requests_counter.labels(
        service="ingest",
        method=info.request.method,
        handler=info.modified_handler,
        status=info.modified_status,
    ).inc()


def _observe_duration(info: Info) -> None:
    _duration_histogram.labels(
        service="ingest",
        method=info.request.method,
        handler=info.modified_handler,
        status=info.modified_status,
    ).observe(info.modified_duration)


_instrumentator = Instrumentator(
    should_instrument_requests_inprogress=False,
    excluded_handlers=["/healthz", "/metrics"],
)
_instrumentator.add(_count_requests)
_instrumentator.add(_observe_duration)
_instrumentator.instrument(app).expose(app)

# Routers
app.include_router(auth.router)
app.include_router(webhooks_github.router)
app.include_router(webhooks_github_app.router)
app.include_router(webhooks_argocd.router)
app.include_router(api.router)
app.include_router(chat.router)
app.include_router(clusters.router)
app.include_router(install.router)
app.include_router(integrations_slack.router)
app.include_router(integrations_slack.api_router)
app.include_router(integrations_slack.events_router)
app.include_router(grafana.router)
app.include_router(mcp_connector.router)
app.include_router(prom.router)
app.include_router(relay_internal.router)
app.include_router(settings.router)
app.include_router(settings.installations_router)
app.include_router(settings.onboarding_router)
app.include_router(settings.members_router)


@app.get("/healthz")
async def healthz():
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": str(e)}
