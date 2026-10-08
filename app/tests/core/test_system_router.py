import asyncio

import httpx
import pytest
from fastapi import FastAPI

from app.config import Settings, get_settings
from app.core.system_router import router
from app.db.redis import get_redis
from app.db.session import get_db
from app.keys.enums import ProviderType
from app.monitoring.publisher import EVENTS_QUEUE_KEY


class StubSession:
    def __init__(self, error: Exception | None = None, delay: float = 0) -> None:
        self._error = error
        self._delay = delay

    async def execute(self, *args, **kwargs):
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._error:
            raise self._error


class StubRedis:
    def __init__(self, ping_error: Exception | None = None, queue_length: int = 0, llen_error: Exception | None = None) -> None:
        self._ping_error = ping_error
        self._queue_length = queue_length
        self._llen_error = llen_error
        self.llen_keys: list[str] = []

    async def ping(self) -> bool:
        if self._ping_error:
            raise self._ping_error
        return True

    async def llen(self, key: str) -> int:
        self.llen_keys.append(key)
        if self._llen_error:
            raise self._llen_error
        return self._queue_length


def _client(session, redis, **settings_overrides) -> httpx.AsyncClient:
    app = FastAPI()
    app.include_router(router)

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = lambda: redis
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, **settings_overrides)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_health_is_always_ok_and_touches_no_dependencies():
    async with _client(StubSession(RuntimeError("db down")), StubRedis(ping_error=RuntimeError("redis down"))) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_ready_is_200_when_database_and_redis_respond():
    async with _client(StubSession(), StubRedis()) as client:
        response = await client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"database": "ok", "redis": "ok"}}


async def test_ready_is_503_when_the_database_is_down():
    async with _client(StubSession(ConnectionRefusedError("nope")), StubRedis()) as client:
        response = await client.get("/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["checks"] == {"database": "failed: ConnectionRefusedError", "redis": "ok"}


async def test_ready_is_503_when_redis_is_down():
    async with _client(StubSession(), StubRedis(ping_error=ConnectionError("nope"))) as client:
        response = await client.get("/ready")

    assert response.status_code == 503
    assert response.json()["checks"] == {"database": "ok", "redis": "failed: ConnectionError"}


async def test_ready_reports_every_failing_dependency():
    async with _client(StubSession(RuntimeError("x")), StubRedis(ping_error=RuntimeError("y"))) as client:
        response = await client.get("/ready")

    assert response.status_code == 503
    assert response.json()["checks"] == {"database": "failed: RuntimeError", "redis": "failed: RuntimeError"}


async def test_ready_gives_up_on_a_hanging_dependency_within_the_timeout():
    async with _client(StubSession(delay=5), StubRedis(), READINESS_TIMEOUT_SECONDS=0.05) as client:
        started = asyncio.get_running_loop().time()
        response = await client.get("/ready")
        elapsed = asyncio.get_running_loop().time() - started

    assert response.status_code == 503
    assert response.json()["checks"]["database"] == "failed: TimeoutError"
    assert elapsed < 1


async def test_ready_never_leaks_error_messages_or_connection_strings():
    secret = "postgresql://user:hunter2@db:5432/app"
    async with _client(StubSession(RuntimeError(secret)), StubRedis()) as client:
        response = await client.get("/ready")

    assert "hunter2" not in response.text


async def test_metrics_are_open_when_no_token_is_configured():
    async with _client(StubSession(), StubRedis()) as client:
        response = await client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "http_requests_in_progress" in response.text


async def test_metrics_require_the_bearer_token_when_configured():
    async with _client(StubSession(), StubRedis(), METRICS_TOKEN="s3cret-token") as client:
        missing = await client.get("/metrics")
        wrong = await client.get("/metrics", headers={"authorization": "Bearer nope"})
        basic = await client.get("/metrics", headers={"authorization": "Basic s3cret-token"})
        correct = await client.get("/metrics", headers={"authorization": "Bearer s3cret-token"})

    assert missing.status_code == 401
    assert missing.headers["www-authenticate"] == "Bearer"
    assert wrong.status_code == 401
    assert basic.status_code == 401
    assert correct.status_code == 200


async def test_metrics_expose_key_counts_by_provider_and_status(db_session, key_repo, test_user):
    await key_repo.create(
        user_id=test_user.id, label="a", provider=ProviderType.GEMINI, key_encrypted="c", daily_limit=10
    )
    await key_repo.create(
        user_id=test_user.id, label="b", provider=ProviderType.GEMINI, key_encrypted="c", daily_limit=10
    )
    await key_repo.create(
        user_id=test_user.id, label="c", provider=ProviderType.GROQ, key_encrypted="c", daily_limit=10
    )

    async with _client(db_session, StubRedis()) as client:
        body = (await client.get("/metrics")).text

    assert 'gateway_keys{provider="gemini",status="active"} 2.0' in body
    assert 'gateway_keys{provider="groq",status="active"} 1.0' in body
    assert 'gateway_keys{provider="openrouter",status="active"} 0.0' in body
    assert 'gateway_keys{provider="gemini",status="cooldown"} 0.0' in body


async def test_metrics_expose_the_events_queue_length():
    redis = StubRedis(queue_length=42)

    async with _client(StubSession(), redis) as client:
        body = (await client.get("/metrics")).text

    assert "gateway_events_queue_length 42.0" in body
    assert redis.llen_keys == [EVENTS_QUEUE_KEY]


async def test_metrics_still_respond_when_the_database_and_redis_are_unavailable():
    redis = StubRedis(llen_error=ConnectionError("redis down"))

    async with _client(StubSession(RuntimeError("db down")), redis) as client:
        response = await client.get("/metrics")

    assert response.status_code == 200
    assert "http_requests_in_progress" in response.text
    assert "gateway_keys{" not in response.text


@pytest.mark.parametrize("path", ["/health", "/ready", "/metrics"])
async def test_system_endpoints_need_no_authentication(path):
    async with _client(StubSession(), StubRedis()) as client:
        response = await client.get(path)

    assert response.status_code in (200, 503)
