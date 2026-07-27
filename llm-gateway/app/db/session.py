from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        str(settings.DATABASE_URL),
        echo=settings.DB_ECHO,
        pool_pre_ping=True,
        # A pet-project-scale pool: generous enough for a few concurrent
        # requests, small enough not to overwhelm a small Postgres instance.
        pool_size=5,
        max_overflow=10,
    )


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=get_engine(),
        expire_on_commit=False,
        autoflush=False,
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a request-scoped AsyncSession."""
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        yield session
