import os

# Settings requires ENCRYPTION_KEY / ADMIN_API_KEY — set dummies before any
# llm_gateway import happens, so get_settings() doesn't blow up on import.
os.environ.setdefault("ENCRYPTION_KEY", "kQ80G5wq1v3o2r7m6b8p3s5t9u1w4y6a8c0e2g4i6k8=")
os.environ.setdefault("ADMIN_API_KEY", "test-admin-key")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from llm_gateway.db.base import Base
from llm_gateway.keys.repository import APIKeyRepository


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """In-memory SQLite for repository-level tests — fast, no external deps.

    Note: SQLite's ENUM handling and lack of true concurrency mean this is
    fine for unit tests of query logic, but integration tests against real
    Postgres (e.g. in CI with a service container) are recommended before
    relying on this alone for anything concurrency-sensitive.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def key_repo(db_session: AsyncSession) -> APIKeyRepository:
    return APIKeyRepository(db_session)


class FakeRedis:
    """Minimal in-memory stand-in for redis.asyncio.Redis, covering just
    the operations our code actually uses (get/set/delete/incr).
    """

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = value

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def incr(self, key: str) -> int:
        current = int(self._store.get(key, "0")) + 1
        self._store[key] = str(current)
        return current


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()
