import os
import ssl
from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Supabase signs its pooler certs with its own private CA (not a public
# one), so full verification needs this root explicitly trusted.
_SUPABASE_CA_PATH = Path(__file__).parent / "certs" / "supabase-root-2021-ca.pem"


def _supabase_ssl_context() -> ssl.SSLContext:
    """Build a fully-verifying (chain + hostname) SSLContext for Supabase.

    Deliberately NOT ssl.create_default_context(): that enables OpenSSL's
    strict X.509 chain-building mode (ssl.VERIFY_X509_STRICT), which
    rejects Supabase's own "Supabase Intermediate 2021 CA" cert — it's a
    real CA:TRUE intermediate but omits the X.509v3 Key Usage extension
    entirely (confirmed via `openssl s_client -showcerts` against the
    live pooler: verify error 19, "self-signed certificate in certificate
    chain", pointing at the self-signed root because strict mode refuses
    to walk through the malformed intermediate). A plain SSLContext with
    strict mode off (the OpenSSL/Python default) and the root CA loaded
    performs full chain + hostname verification successfully — this is a
    defect in Supabase's cert, not a reason to skip verification.
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(cafile=str(_SUPABASE_CA_PATH))
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = True
    return context


def prepare_database_url(url: str) -> tuple[str, dict]:
    """Normalize a DATABASE_URL to the asyncpg dialect and work out the
    connect_args a Supabase host needs.

    Supabase requires TLS and doesn't reliably negotiate it from the URL
    alone across asyncpg versions, so pass it explicitly. The local-dev
    compose Postgres (--profile local-db) has no TLS listener at all, so
    only do this for a Supabase host.
    """
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    connect_args: dict = {}
    if "supabase" in url:
        connect_args["ssl"] = _supabase_ssl_context()
        # Transaction-mode pooler (port 6543) doesn't support asyncpg's
        # server-side prepared statements. We default to the session
        # pooler (5432), but disable statement caching unconditionally
        # if DATABASE_URL ever points at 6543 instead — cheap insurance
        # against a bad rotation.
        if ":6543" in url:
            connect_args["statement_cache_size"] = 0
    return url, connect_args


DATABASE_URL, _connect_args = prepare_database_url(
    os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://kubex:kubex@localhost:5432/kubex",
    )
)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=1800,
    connect_args=_connect_args,
)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
