import logging

from llm_gateway.db.redis import get_redis
from llm_gateway.db.session import get_sessionmaker
from llm_gateway.keys.cache import KeyStatusCache
from llm_gateway.keys.enums import ProviderType
from llm_gateway.keys.repository import APIKeyRepository
from llm_gateway.config import get_settings

logger = logging.getLogger(__name__)


async def clear_expired_cooldowns(ctx: dict) -> None:
    """Runs frequently (e.g. every 5 min): bring COOLDOWN keys back to ACTIVE
    once their cooldown_until has passed. Cheap, idempotent.
    """
    session_factory = get_sessionmaker()
    settings = get_settings()
    redis = get_redis()
    cache = KeyStatusCache(redis, ttl_seconds=settings.KEY_STATUS_CACHE_TTL_SECONDS)

    async with session_factory() as session:
        repo = APIKeyRepository(session)
        affected = await repo.clear_expired_cooldowns()

    if affected:
        logger.info("clear_expired_cooldowns: revived %d key(s)", affected)
        for provider in ProviderType:
            await cache.invalidate(provider.value)


async def reset_daily_limits(ctx: dict) -> None:
    """Runs on a daily cron: zero requests_today and revive eligible keys.

    EXHAUSTED keys are revived here too (daily quota resets upstream);
    DISABLED keys are intentionally left alone — that's a manual decision.
    """
    session_factory = get_sessionmaker()
    settings = get_settings()
    redis = get_redis()
    cache = KeyStatusCache(redis, ttl_seconds=settings.KEY_STATUS_CACHE_TTL_SECONDS)

    async with session_factory() as session:
        repo = APIKeyRepository(session)
        affected = await repo.reset_daily_counters()

    logger.info("reset_daily_limits: reset %d key(s)", affected)
    for provider in ProviderType:
        await cache.invalidate(provider.value)
