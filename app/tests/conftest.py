import os
from typing import Self

os.environ.setdefault("ENCRYPTION_KEY", "kQ80G5wq1v3o2r7m6b8p3s5t9u1w4y6a8c0e2g4i6k8=")
os.environ.setdefault("ADMIN_API_KEY", "test-admin-key")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key")
os.environ.setdefault("SESSION_SECRET_KEY", "test-session-secret-key")

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.models import User
from app.auth.repository import RefreshTokenRepository, UserRepository
from app.db.base import Base
from app.keys.repository import APIKeyRepository
from app.tokens.repository import GatewayTokenRepository


def _register_date_trunc(dbapi_connection, connection_record) -> None:
    """Make Postgres's date_trunc('day', ts) work against the SQLite test DB.

    Production runs on Postgres, which has date_trunc natively (see
    app.monitoring.publisher). SQLite doesn't, so queries that group by day
    (daily_timeseries, tokens_by_provider_daily, latency_percentiles_daily's
    day bucketing) would fail on every DB-backed test without this. Only
    "day" truncation is implemented since that's the only granularity the
    codebase currently uses.

    Note: this does NOT make percentile_cont/WITHIN GROUP work — that's
    genuine PostgreSQL syntax with no SQLite equivalent, UDF or otherwise.
    Tests that need it are skipped with an explanation (see test_publisher.py).
    """

    def date_trunc(part: str, value: str | None) -> str | None:
        if value is None:
            return None
        if part == "day":
            return str(value)[:10] + " 00:00:00"
        raise NotImplementedError(f"date_trunc granularity {part!r} not supported by the SQLite test shim")

    dbapi_connection.create_function("date_trunc", 2, date_trunc)


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    event.listen(engine.sync_engine, "connect", _register_date_trunc)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def key_repo(db_session: AsyncSession) -> APIKeyRepository:
    return APIKeyRepository(db_session)


@pytest_asyncio.fixture
async def token_repo(db_session: AsyncSession) -> GatewayTokenRepository:
    return GatewayTokenRepository(db_session)


@pytest_asyncio.fixture
async def user_repo(db_session: AsyncSession) -> UserRepository:
    return UserRepository(db_session)


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    user = User(google_sub="test-google-sub-1", email="owner@example.com", display_name="Owner")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def other_user(db_session: AsyncSession) -> User:
    user = User(google_sub="test-google-sub-2", email="other@example.com", display_name="Other")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def refresh_token_repo(db_session: AsyncSession) -> RefreshTokenRepository:
    return RefreshTokenRepository(db_session)


class FakePipeline:
    def __init__(self, redis: "FakeRedis") -> None:
        self._redis = redis
        self._ops: list[tuple[str, tuple]] = []

    def publish(self, channel: str, message: str) -> None:
        self._ops.append(("publish", (channel, message)))

    def lpush(self, key: str, value: str) -> None:
        self._ops.append(("lpush", (key, value)))

    def ltrim(self, key: str, start: int, end: int) -> None:
        self._ops.append(("ltrim", (key, start, end)))

    def rpop(self, key: str) -> None:
        self._ops.append(("rpop", (key,)))

    async def execute(self) -> list:
        results = []
        for name, args in self._ops:
            results.append(await getattr(self._redis, name)(*args))
        return results

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info) -> None:
        return None


class FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._lists: dict[str, list[str]] = {}
        self.published: list[tuple[str, str]] = []

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

    async def publish(self, channel: str, message: str) -> None:
        self.published.append((channel, message))

    async def lpush(self, key: str, value: str) -> None:
        self._lists.setdefault(key, []).insert(0, value)

    async def ltrim(self, key: str, start: int, end: int) -> None:
        items = self._lists.get(key, [])
        self._lists[key] = items[start : end + 1]

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        items = self._lists.get(key, [])
        if end == -1:
            return items[start:]
        return items[start : end + 1]

    async def rpop(self, key: str) -> str | None:
        items = self._lists.get(key)
        if not items:
            return None
        return items.pop()

    def pipeline(self, transaction: bool = True) -> FakePipeline:
        return FakePipeline(self)


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()
