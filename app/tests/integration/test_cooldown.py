import asyncio

import pytest

from app.keys.cache import KeyStatusCache
from app.keys.enums import KeyStatus, ProviderType
from app.keys.repository import APIKeyRepository
from app.keys.schemas import APIKeyCreate
from app.keys.selector import RoundRobinSelector
from app.keys.service import KeyPoolService

pytestmark = pytest.mark.integration


async def test_cooling_key_returns_to_the_pool_when_its_cooldown_ends_in_real_postgres_and_redis(
    db_session, test_user, redis_client
):
    repository = APIKeyRepository(db_session)
    pool = KeyPoolService(repository, KeyStatusCache(redis_client, ttl_seconds=30), RoundRobinSelector(redis_client))
    key = await pool.create_key(
        test_user.id,
        APIKeyCreate(label="k", provider=ProviderType.GROQ, raw_key="raw-key", daily_limit=100),
    )

    await pool.record_rate_limited(key.id, test_user.id, ProviderType.GROQ, retry_after_seconds=1)

    assert await pool.get_candidate_keys(test_user.id, ProviderType.GROQ) == []
    cache_key = pool._cache._cache_key(test_user.id, ProviderType.GROQ.value)
    assert 0 < await redis_client.ttl(cache_key) <= 1

    await asyncio.sleep(1.3)
    candidates = await pool.get_candidate_keys(test_user.id, ProviderType.GROQ)

    assert [c.id for c in candidates] == [key.id]
    assert (await repository.get(key.id, user_id=test_user.id)).status == KeyStatus.ACTIVE
