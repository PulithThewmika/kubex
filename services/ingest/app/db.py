import os
import ssl
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

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
        connect_args["ssl"] = ssl.create_default_context()
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
