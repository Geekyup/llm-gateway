import logging

from app.config import get_settings
from app.db.redis import get_redis
from app.db.session import get_sessionmaker
from app.keys.cache import KeyStatusCache
from app.keys.enums import KeyStatus
from app.keys.repository import APIKeyRepository
from app.keys.selector import RoundRobinSelector
from app.keys.service import KeyPoolService

logger = logging.getLogger(__name__)


async def clear_expired_cooldowns(ctx: dict) -> None:
    session_factory = get_sessionmaker()
    settings = get_settings()
    redis = get_redis()
    cache = KeyStatusCache(redis, ttl_seconds=settings.KEY_STATUS_CACHE_TTL_SECONDS)

    async with session_factory() as session:
        repo = APIKeyRepository(session)
        revived_keys = await repo.clear_expired_cooldowns()

    if revived_keys:
        logger.info("clear_expired_cooldowns: revived %d key(s)", len(revived_keys))
        touched = {(key.user_id, key.provider.value) for key in revived_keys}
        for user_id, provider_value in touched:
            await cache.invalidate(user_id, provider_value)


async def reset_daily_limits(ctx: dict) -> None:
    session_factory = get_sessionmaker()
    settings = get_settings()
    redis = get_redis()
    cache = KeyStatusCache(redis, ttl_seconds=settings.KEY_STATUS_CACHE_TTL_SECONDS)

    async with session_factory() as session:
        repo = APIKeyRepository(session)
        reset_keys = await repo.reset_daily_counters()

    logger.info("reset_daily_limits: reset %d key(s)", len(reset_keys))
    touched = {(key.user_id, key.provider.value) for key in reset_keys}
    for user_id, provider_value in touched:
        await cache.invalidate(user_id, provider_value)


async def health_check_exhausted_keys(ctx: dict) -> None:
    session_factory = get_sessionmaker()
    settings = get_settings()
    redis = get_redis()
    cache = KeyStatusCache(redis, ttl_seconds=settings.KEY_STATUS_CACHE_TTL_SECONDS)

    async with session_factory() as session:
        repo = APIKeyRepository(session)
        selector = RoundRobinSelector(redis)
        service = KeyPoolService(repo, cache, selector)

        all_keys = await repo.list_all_system_wide()
        exhausted = [k for k in all_keys if k.status == KeyStatus.EXHAUSTED]
        revived = 0
        for key in exhausted:
            result = await service.check_key_health(key.id, key.user_id)
            if result.ok:
                revived += 1

    if exhausted:
        logger.info("health_check_exhausted_keys: checked %d, revived %d", len(exhausted), revived)
