import asyncio
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.gateway.dependencies import _enforce_rate_limit
from app.keys.cache import KeyStatusCache
from app.keys.enums import KeyStatus, ProviderType
from app.keys.models import APIKey
from app.keys.schemas import APIKeyDTO
from app.keys.selector import RoundRobinSelector
from app.monitoring.models import RequestEventRecord
from app.monitoring.publisher import EVENTS_QUEUE_KEY, RequestEventPublisher, drain_event_queue
from app.monitoring.schemas import RequestEvent

pytestmark = pytest.mark.integration


def _dto(key_id: int) -> APIKeyDTO:
    return APIKeyDTO(
        id=key_id,
        user_id=1,
        label=f"k{key_id}",
        provider=ProviderType.GEMINI,
        status=KeyStatus.ACTIVE,
        requests_today=0,
        daily_limit=100,
        key_encrypted="ciphertext",
    )


async def test_cache_roundtrip_sets_a_ttl_and_never_stores_plaintext(redis_client):
    cache = KeyStatusCache(redis_client, ttl_seconds=30)

    await cache.set_active(1, "gemini", [_dto(1), _dto(2)])

    key = cache._cache_key(1, "gemini")
    ttl = await redis_client.ttl(key)
    assert 0 < ttl <= 30
    assert "decrypted_key" not in await redis_client.get(key)
    restored = await cache.get_active(1, "gemini")
    assert [dto.id for dto in restored] == [1, 2]

    await cache.invalidate(1, "gemini")
    assert await cache.get_active(1, "gemini") is None


async def test_cache_entry_expires_on_its_own(redis_client):
    cache = KeyStatusCache(redis_client, ttl_seconds=1)

    await cache.set_active(1, "gemini", [_dto(1)])
    await asyncio.sleep(1.2)

    assert await cache.get_active(1, "gemini") is None


async def test_round_robin_is_fair_under_concurrency(redis_client):
    selector = RoundRobinSelector(redis_client)
    candidates = [_dto(1), _dto(2), _dto(3)]

    picks = await asyncio.gather(*(selector.select(1, "gemini", candidates) for _ in range(99)))

    counts = {dto.id: sum(p.id == dto.id for p in picks) for dto in candidates}
    assert counts == {1: 33, 2: 33, 3: 33}


async def test_rate_limit_counter_expires_and_blocks_over_the_limit(redis_client):
    from fastapi import HTTPException

    for _ in range(3):
        await _enforce_rate_limit(redis_client, user_id=1, limit=3)

    with pytest.raises(HTTPException) as exc_info:
        await _enforce_rate_limit(redis_client, user_id=1, limit=3)

    assert exc_info.value.status_code == 429
    keys = await redis_client.keys("ratelimit:gateway:1:*")
    assert len(keys) == 1
    assert 0 < await redis_client.ttl(keys[0]) <= 120


async def test_events_flow_from_redis_queue_into_postgres_in_order(db_session, test_user, redis_client):
    key = APIKey(
        user_id=test_user.id,
        label="k",
        provider=ProviderType.GEMINI,
        key_encrypted="c",
        daily_limit=10,
        status=KeyStatus.ACTIVE,
    )
    db_session.add(key)
    await db_session.commit()
    publisher = RequestEventPublisher(redis=redis_client)

    for index in range(25):
        await publisher.publish(
            RequestEvent(
                user_id=test_user.id,
                request_id=f"req-{index:02d}",
                attempt=1,
                timestamp=datetime.now(UTC),
                provider="gemini",
                path="v1/x",
                method="POST",
                key_id=key.id,
                key_label="k",
                upstream_status=200,
                outcome="success",
                latency_ms=10,
                is_retry=False,
            )
        )
    assert await redis_client.llen(EVENTS_QUEUE_KEY) == 25

    drained = [await drain_event_queue(redis_client, db_session, batch_size=10) for _ in range(3)]

    assert drained == [10, 10, 5]
    assert await redis_client.llen(EVENTS_QUEUE_KEY) == 0
    request_ids = (
        await db_session.execute(select(RequestEventRecord.request_id).order_by(RequestEventRecord.id))
    ).scalars().all()
    assert request_ids == [f"req-{index:02d}" for index in range(25)]
