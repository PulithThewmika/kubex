from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import DATABASE_CONNECT_ARGS, DATABASE_URL

# Agent is a single-loop batch process (one 60s tick), not a concurrent
# request handler — a small pool is plenty and keeps it light on
# Supabase's connection limit.
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=3,
    max_overflow=2,
    connect_args=DATABASE_CONNECT_ARGS,
)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncSession:
    return async_session()


async def dispose_engine() -> None:
    await engine.dispose()
