import asyncio
from datetime import UTC, datetime

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis

from app.config import Settings, get_settings
from app.core.system_router import router
from app.db.redis import get_redis
from app.db.session import get_db
from app.keys.enums import ProviderType
from app.keys.repository import APIKeyRepository
from app.monitoring.cache import ActivityCache
from app.monitoring.publisher import RequestEventPublisher
from app.monitoring.schemas import ActivitySummary, RequestEvent

pytestmark = pytest.mark.integration


def _client(db_session, redis) -> httpx.AsyncClient:
    app = FastAPI()
    app.include_router(router)

    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = lambda: redis
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, READINESS_TIMEOUT_SECONDS=2)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_ready_is_200_against_real_postgres_and_redis(db_session, redis_client):
    async with _client(db_session, redis_client) as client:
        response = await client.get("/ready")

    assert response.status_code == 200
    assert response.json()["checks"] == {"database": "ok", "redis": "ok"}


async def test_ready_is_503_and_names_redis_when_it_is_unreachable(db_session):
    dead_redis = Redis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=0.5)
    try:
        async with _client(db_session, dead_redis) as client:
            response = await client.get("/ready")
    finally:
        await dead_redis.aclose()

    assert response.status_code == 503
    assert response.json()["checks"]["database"] == "ok"
    assert response.json()["checks"]["redis"].startswith("failed: ")


async def test_metrics_reflect_real_key_rows_and_the_real_events_queue(db_session, test_user, redis_client):
    await APIKeyRepository(db_session).create(
        user_id=test_user.id, label="k", provider=ProviderType.GROQ, key_encrypted="c", daily_limit=10
    )
    publisher = RequestEventPublisher(redis=redis_client)
    for index in range(3):
        await publisher.publish(
            RequestEvent(
                user_id=test_user.id,
                request_id=f"req-{index}",
                attempt=1,
                timestamp=datetime.now(UTC),
                provider="groq",
                path="v1/x",
                method="POST",
                key_id=None,
                key_label=None,
                upstream_status=200,
                outcome="success",
                latency_ms=10,
                is_retry=False,
            )
        )

    async with _client(db_session, redis_client) as client:
        body = (await client.get("/metrics")).text

    assert 'gateway_keys{provider="groq",status="active"} 1.0' in body
    assert "gateway_events_queue_length 3.0" in body


async def test_activity_cache_entry_expires_in_real_redis(redis_client):
    cache = ActivityCache(redis_client, ttl_seconds=1)
    calls = 0

    async def loader() -> ActivitySummary:
        nonlocal calls
        calls += 1
        return ActivitySummary(
            total_requests=calls,
            prev_total_requests=0,
            success_rate=100.0,
            prev_success_rate=0.0,
            total_tokens=0,
            prev_total_tokens=0,
        )

    async def load():
        return await cache.get_or_load(
            user_id=1, endpoint="summary", params="7d", model=ActivitySummary, loader=loader
        )

    first = await load()
    key = "activity:v1:1:summary:7d"
    assert 0 < await redis_client.ttl(key) <= 1
    cached = await load()
    await asyncio.sleep(1.2)
    reloaded = await load()

    assert (first.total_requests, cached.total_requests, reloaded.total_requests) == (1, 1, 2)
