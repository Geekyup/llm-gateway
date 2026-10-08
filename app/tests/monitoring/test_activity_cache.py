from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from prometheus_client import REGISTRY

from app.api.deps import get_activity_cache, get_event_publisher
from app.auth.deps import get_current_user
from app.monitoring.activity_router import router
from app.monitoring.cache import ActivityCache
from app.monitoring.schemas import ActivitySummary, TopModelsResponse


def _summary(total: int = 5) -> ActivitySummary:
    return ActivitySummary(
        total_requests=total,
        prev_total_requests=3,
        success_rate=100.0,
        prev_success_rate=90.0,
        latency_p50=100.0,
        latency_p95=200.0,
        prev_latency_p95=250.0,
        total_tokens=10,
        prev_total_tokens=8,
    )


def _sample(name: str, **labels) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


class Loader:
    def __init__(self, *totals: int) -> None:
        self._totals = list(totals) or [5]
        self.calls = 0

    async def __call__(self) -> ActivitySummary:
        total = self._totals[min(self.calls, len(self._totals) - 1)]
        self.calls += 1
        return _summary(total)


class BrokenRedis:
    async def get(self, key: str):
        raise ConnectionError("redis down")

    async def set(self, key: str, value: str, ex: int | None = None):
        raise ConnectionError("redis down")


async def _load(cache: ActivityCache, loader, *, user_id: int = 1, endpoint: str = "summary", params: str = "7d"):
    return await cache.get_or_load(
        user_id=user_id, endpoint=endpoint, params=params, model=ActivitySummary, loader=loader
    )


async def test_second_call_is_served_from_the_cache(fake_redis):
    cache = ActivityCache(fake_redis, ttl_seconds=30)
    loader = Loader(5, 99)

    first = await _load(cache, loader)
    second = await _load(cache, loader)

    assert first.total_requests == 5
    assert second.total_requests == 5
    assert loader.calls == 1


async def test_entries_are_namespaced_per_user_endpoint_and_params(fake_redis):
    cache = ActivityCache(fake_redis, ttl_seconds=30)
    loader = Loader(1, 2, 3, 4)

    await _load(cache, loader, user_id=1, params="7d")
    await _load(cache, loader, user_id=2, params="7d")
    await _load(cache, loader, user_id=1, params="24h")
    await _load(cache, loader, user_id=1, endpoint="other", params="7d")

    assert loader.calls == 4
    assert await fake_redis.get("activity:v1:1:summary:7d") is not None
    assert await fake_redis.get("activity:v1:2:summary:7d") is not None


async def test_zero_ttl_disables_caching_entirely(fake_redis):
    cache = ActivityCache(fake_redis, ttl_seconds=0)
    loader = Loader()

    await _load(cache, loader)
    await _load(cache, loader)

    assert loader.calls == 2
    assert await fake_redis.get("activity:v1:1:summary:7d") is None


async def test_entry_is_stored_with_the_configured_ttl():
    writes: list[tuple[str, int | None]] = []

    class RecordingRedis:
        async def get(self, key: str):
            return None

        async def set(self, key: str, value: str, ex: int | None = None):
            writes.append((key, ex))

    await _load(ActivityCache(RecordingRedis(), ttl_seconds=45), Loader())

    assert writes == [("activity:v1:1:summary:7d", 45)]


async def test_redis_failures_fall_back_to_the_loader_instead_of_failing_the_request():
    cache = ActivityCache(BrokenRedis(), ttl_seconds=30)
    loader = Loader(5, 6)

    first = await _load(cache, loader)
    second = await _load(cache, loader)

    assert (first.total_requests, second.total_requests) == (5, 6)
    assert loader.calls == 2


async def test_corrupt_cache_entry_is_reloaded_and_overwritten(fake_redis):
    await fake_redis.set("activity:v1:1:summary:7d", "{not valid json", ex=30)
    cache = ActivityCache(fake_redis, ttl_seconds=30)
    loader = Loader(7)

    value = await _load(cache, loader)
    again = await _load(cache, loader)

    assert value.total_requests == 7
    assert again.total_requests == 7
    assert loader.calls == 1


async def test_hits_and_misses_are_counted(fake_redis):
    cache = ActivityCache(fake_redis, ttl_seconds=30)
    hits = _sample("activity_cache_requests_total", endpoint="metrics-test", result="hit")
    misses = _sample("activity_cache_requests_total", endpoint="metrics-test", result="miss")

    await _load(cache, Loader(), endpoint="metrics-test")
    await _load(cache, Loader(), endpoint="metrics-test")
    await _load(cache, Loader(), endpoint="metrics-test")

    assert _sample("activity_cache_requests_total", endpoint="metrics-test", result="hit") - hits == 2
    assert _sample("activity_cache_requests_total", endpoint="metrics-test", result="miss") - misses == 1


class CountingPublisher:
    def __init__(self) -> None:
        self.summary_calls = 0
        self.top_models_calls = 0
        self.log_calls = 0

    async def activity_summary(self, user_id: int, range: str) -> ActivitySummary:
        self.summary_calls += 1
        return _summary(self.summary_calls)

    async def top_models(self, user_id: int, range: str, limit: int = 10) -> list:
        self.top_models_calls += 1
        return []

    async def activity_log(self, user_id: int, range: str, **kwargs):
        self.log_calls += 1
        return [], 0


@pytest.fixture
def publisher() -> CountingPublisher:
    return CountingPublisher()


@pytest.fixture
async def client(publisher, fake_redis):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
    app.dependency_overrides[get_event_publisher] = lambda: publisher
    app.dependency_overrides[get_activity_cache] = lambda: ActivityCache(fake_redis, ttl_seconds=30)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


async def test_endpoint_hits_the_database_once_for_repeated_requests(client, publisher):
    first = await client.get("/me/activity/summary?range=7d")
    second = await client.get("/me/activity/summary?range=7d")

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert publisher.summary_calls == 1


async def test_switching_ranges_back_and_forth_reuses_cached_results(client, publisher):
    for range_ in ("24h", "7d", "24h", "7d", "24h"):
        await client.get(f"/me/activity/summary?range={range_}")

    assert publisher.summary_calls == 2


async def test_top_models_cache_is_keyed_by_the_limit_too(client, publisher):
    await client.get("/me/activity/top-models?range=7d&limit=5")
    await client.get("/me/activity/top-models?range=7d&limit=10")
    await client.get("/me/activity/top-models?range=7d&limit=5")

    assert publisher.top_models_calls == 2


async def test_cached_response_keeps_the_declared_shape(client):
    await client.get("/me/activity/top-models?range=24h&limit=3")
    cached = await client.get("/me/activity/top-models?range=24h&limit=3")

    assert TopModelsResponse.model_validate(cached.json()).range == "24h"


async def test_activity_log_is_not_cached(client, publisher):
    await client.get("/me/activity/log?range=7d")
    await client.get("/me/activity/log?range=7d")

    assert publisher.log_calls == 2
