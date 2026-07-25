import os

# Settings requires ENCRYPTION_KEY / ADMIN_API_KEY — set dummies before any
# llm_gateway import happens, so get_settings() doesn't blow up on import.
os.environ.setdefault("ENCRYPTION_KEY", "kQ80G5wq1v3o2r7m6b8p3s5t9u1w4y6a8c0e2g4i6k8=")
os.environ.setdefault("ADMIN_API_KEY", "test-admin-key")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key")
os.environ.setdefault("SESSION_SECRET_KEY", "test-session-secret-key")

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.models import User
from app.auth.repository import RefreshTokenRepository, UserRepository
from app.db.base import Base
from app.keys.repository import APIKeyRepository
from app.tokens.repository import GatewayTokenRepository


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


@pytest_asyncio.fixture
async def token_repo(db_session: AsyncSession) -> GatewayTokenRepository:
    return GatewayTokenRepository(db_session)


@pytest_asyncio.fixture
async def user_repo(db_session: AsyncSession) -> UserRepository:
    return UserRepository(db_session)


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """A real persisted User row — api_keys/gateway_tokens now have a
    NOT NULL FK to users.id, so key/token tests need an owner to point at.
    """
    user = User(google_sub="test-google-sub-1", email="owner@example.com", display_name="Owner")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def other_user(db_session: AsyncSession) -> User:
    """A second, distinct owner — for isolation tests (user A can't touch
    user B's keys/tokens/events).
    """
    user = User(google_sub="test-google-sub-2", email="other@example.com", display_name="Other")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def refresh_token_repo(db_session: AsyncSession) -> RefreshTokenRepository:
    return RefreshTokenRepository(db_session)


class FakePipeline:
    """Minimal stand-in for redis.asyncio.Redis.pipeline(transaction=False).

    Just queues (method_name, args) tuples and replays them against the
    parent FakeRedis on execute() — enough for RequestEventPublisher, which
    only needs publish/lpush/ltrim batched together.
    """

    def __init__(self, redis: "FakeRedis") -> None:
        self._redis = redis
        self._ops: list[tuple[str, tuple]] = []

    def publish(self, channel: str, message: str) -> None:
        self._ops.append(("publish", (channel, message)))

    def lpush(self, key: str, value: str) -> None:
        self._ops.append(("lpush", (key, value)))

    def ltrim(self, key: str, start: int, end: int) -> None:
        self._ops.append(("ltrim", (key, start, end)))

    async def execute(self) -> list:
        results = []
        for name, args in self._ops:
            results.append(await getattr(self._redis, name)(*args))
        return results

    async def __aenter__(self) -> "FakePipeline":
        return self

    async def __aexit__(self, *exc_info) -> None:
        return None


class FakeRedis:
    """Minimal in-memory stand-in for redis.asyncio.Redis, covering just
    the operations our code actually uses (get/set/delete/incr, plus
    pub/sub-adjacent list ops for the live monitoring feature).
    """

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
        # Redis LTRIM end index is inclusive.
        self._lists[key] = items[start : end + 1]

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        items = self._lists.get(key, [])
        if end == -1:
            return items[start:]
        return items[start : end + 1]

    def pipeline(self, transaction: bool = True) -> FakePipeline:
        return FakePipeline(self)


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()
