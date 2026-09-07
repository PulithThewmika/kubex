import os
import re
import ssl
from pathlib import Path
from urllib.parse import urlsplit


def _parse_duration(value: str) -> int:
    """Parse a duration string like '30m', '1h', '15m' into seconds."""
    match = re.fullmatch(r"(\d+)\s*([smh])", value.strip().lower())
    if not match:
        raise ValueError(f"Invalid duration format: {value!r}. Use e.g. '30m', '1h', '90s'.")
    amount, unit = int(match.group(1)), match.group(2)
    multipliers = {"s": 1, "m": 60, "h": 3600}
    return amount * multipliers[unit]


# Supabase signs its pooler certs with its own private CA (not a public
# one), so full verification needs this root explicitly trusted.
_SUPABASE_CA_PATH = Path(__file__).parent / "certs" / "supabase-root-2021-ca.pem"


def _supabase_ssl_context() -> ssl.SSLContext:
    """Build a fully-verifying (chain + hostname) SSLContext for Supabase.

    See services/ingest/app/db.py's identical helper for why this is a
    plain SSLContext rather than ssl.create_default_context(): the latter
    enables OpenSSL's strict X.509 mode, which rejects Supabase's own
    intermediate CA cert (a real defect on their side — it's missing the
    Key Usage extension). A non-strict context with the root CA loaded
    verifies the full chain and hostname correctly.
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(cafile=str(_SUPABASE_CA_PATH))
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = True
    return context


_SUPABASE_HOST_SUFFIXES = (".supabase.co", ".supabase.com")


def _is_supabase_host(url: str) -> bool:
    """See services/ingest/app/db.py's identical helper for why this
    parses the hostname rather than doing a raw "supabase" in url
    substring check (case-sensitivity and false-positive/negative risk).
    """
    hostname = urlsplit(url).hostname
    if hostname is None:
        return False
    hostname = hostname.rstrip(".")  # a fully-qualified DNS name may have a trailing root dot
    return hostname.endswith(_SUPABASE_HOST_SUFFIXES)


def prepare_database_url(url: str) -> tuple[str, dict]:
    """Normalize a DATABASE_URL to the asyncpg dialect and work out the
    connect_args a Supabase host needs. Rejects the transaction-mode
    pooler (:6543) outright — see services/ingest/app/db.py's identical
    function for why. The local-dev compose Postgres (--profile
    local-db) has no TLS listener, so this is a no-op for it.
    """
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    connect_args: dict = {}
    if _is_supabase_host(url):
        connect_args["ssl"] = _supabase_ssl_context()
        if urlsplit(url).port == 6543:
            raise ValueError(
                "DATABASE_URL points at Supabase's transaction-mode pooler "
                "(port 6543), which this codebase does not support — "
                "prepared statements break under transaction pooling even "
                "with asyncpg's statement cache disabled, since SQLAlchemy's "
                "asyncpg dialect keeps its own separate prepared-statement "
                "cache. Use the session pooler (port 5432) instead."
            )
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
