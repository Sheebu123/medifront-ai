"""Lazy asynchronous SQLAlchemy engine and request-scoped sessions."""

from collections.abc import AsyncIterator
from functools import lru_cache

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import DatabaseConfigurationError, get_database_url


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """Create the async psycopg engine on first database use, not at import."""
    database_url = get_database_url()
    return create_async_engine(database_url, pool_pre_ping=True)


@lru_cache(maxsize=1)
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return one reusable async session factory for this application process."""
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield a database session or return a stable setup error when unconfigured."""
    try:
        factory = get_session_factory()
    except DatabaseConfigurationError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The application database is not configured.",
        ) from None

    async with factory() as session:
        yield session


async def dispose_database_engine() -> None:
    """Dispose the cached engine, primarily for orderly application shutdown."""
    if get_engine.cache_info().currsize:
        await get_engine().dispose()
        get_session_factory.cache_clear()
        get_engine.cache_clear()
