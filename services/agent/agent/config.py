import os
import re
import ssl


def _parse_duration(value: str) -> int:
    """Parse a duration string like '30m', '1h', '15m' into seconds."""
    match = re.fullmatch(r"(\d+)\s*([smh])", value.strip().lower())
    if not match:
        raise ValueError(f"Invalid duration format: {value!r}. Use e.g. '30m', '1h', '90s'.")
    amount, unit = int(match.group(1)), match.group(2)
    multipliers = {"s": 1, "m": 60, "h": 3600}
    return amount * multipliers[unit]


def prepare_database_url(url: str) -> tuple[str, dict]:
    """Normalize a DATABASE_URL to the asyncpg dialect and work out the
    connect_args a Supabase host needs (TLS, and disabled statement
    caching if pointed at the transaction-mode pooler on :6543). The
    local-dev compose Postgres (--profile local-db) has no TLS listener,
    so this is a no-op for it.
    """
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    connect_args: dict = {}
    if "supabase" in url:
        connect_args["ssl"] = ssl.create_default_context()
        if ":6543" in url:
            connect_args["statement_cache_size"] = 0
    return url, connect_args


DATABASE_URL, DATABASE_CONNECT_ARGS = prepare_database_url(
    os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://kubex:kubex@localhost:5432/kubex",
    )
)

PROM_URL = os.environ.get("PROM_URL", "http://localhost:9090")

ALERTMANAGER_URL = os.environ.get("ALERTMANAGER_URL", "http://localhost:9093")

BASELINE_WINDOW = os.environ.get("BASELINE_WINDOW", "30m")
BASELINE_WINDOW_SECONDS = _parse_duration(BASELINE_WINDOW)

OBSERVATION_WINDOW = os.environ.get("OBSERVATION_WINDOW", "15m")
OBSERVATION_WINDOW_SECONDS = _parse_duration(OBSERVATION_WINDOW)

AGENT_INTERVAL_SECONDS = int(os.environ.get("AGENT_INTERVAL_SECONDS", "60"))

# ── Blast radius discovery (E14-T3) ──────────────────────────────────
# K8s API server this agent discovers service dependencies from. Empty
# means the feature is disabled (opt-in, since it needs a ServiceAccount
# token minted by deploy/scripts/create-blast-radius-sa.sh).
K8S_API_SERVER = os.environ.get("K8S_API_SERVER", "")
K8S_TOKEN = os.environ.get("K8S_TOKEN", "")
K8S_CA_CERT_B64 = os.environ.get("K8S_CA_CERT_B64", "")

BLAST_RADIUS_INTERVAL_SECONDS = int(os.environ.get("BLAST_RADIUS_INTERVAL_SECONDS", "300"))

# ── HTTP health check fallback (E23-T1) ──────────────────────────────
# For services without Prometheus. Ticks on a short fixed interval and
# pings each configured service only once its own health_check_interval_s
# has elapsed, since that's per-service and configurable via the API.
HEALTH_CHECK_TICK_SECONDS = int(os.environ.get("HEALTH_CHECK_TICK_SECONDS", "15"))
if HEALTH_CHECK_TICK_SECONDS <= 0:
    raise ValueError("HEALTH_CHECK_TICK_SECONDS must be a positive integer")

HEALTH_CHECK_RING_BUFFER_SIZE = int(os.environ.get("HEALTH_CHECK_RING_BUFFER_SIZE", "20"))
if HEALTH_CHECK_RING_BUFFER_SIZE <= 0:
    raise ValueError("HEALTH_CHECK_RING_BUFFER_SIZE must be a positive integer")

# Caps how many health checks run at once per tick — an unbounded fan-out
# would let a large service count open that many concurrent connections
# (and DNS lookups) in one go.
HEALTH_CHECK_MAX_CONCURRENCY = int(os.environ.get("HEALTH_CHECK_MAX_CONCURRENCY", "10"))
if HEALTH_CHECK_MAX_CONCURRENCY <= 0:
    raise ValueError("HEALTH_CHECK_MAX_CONCURRENCY must be a positive integer")
