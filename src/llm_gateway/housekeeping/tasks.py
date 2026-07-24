import logging

from llm_gateway.db.redis import get_redis
from llm_gateway.db.session import get_sessionmaker
from llm_gateway.keys.cache import KeyStatusCache
from llm_gateway.keys.enums import KeyStatus
from llm_gateway.keys.repository import APIKeyRepository
from llm_gateway.keys.selector import RoundRobinSelector
from llm_gateway.keys.service import KeyPoolService
from llm_gateway.config import get_settings

logger = logging.getLogger(__name__)


async def clear_expired_cooldowns(ctx: dict) -> None:
    """Runs frequently (e.g. every 5 min): bring COOLDOWN keys back to ACTIVE
    once their cooldown_until has passed. Cheap, idempotent.

    System-wide job — deliberately not scoped to one user, since it walks
    every account's keys on the same schedule.
    """
    session_factory = get_sessionmaker()
    settings = get_settings()
    redis = get_redis()
    cache = KeyStatusCache(redis, ttl_seconds=settings.KEY_STATUS_CACHE_TTL_SECONDS)

    async with session_factory() as session:
        repo = APIKeyRepository(session)
        revived_keys = await repo.clear_expired_cooldowns()

    if revived_keys:
        logger.info("clear_expired_cooldowns: revived %d key(s)", len(revived_keys))
        # Only invalidate the (user_id, provider) pairs actually touched,
        # rather than every user's cache for every provider.
        touched = {(key.user_id, key.provider.value) for key in revived_keys}
        for user_id, provider_value in touched:
            await cache.invalidate(user_id, provider_value)


async def reset_daily_limits(ctx: dict) -> None:
    """Runs on a daily cron: zero requests_today and revive eligible keys.

    EXHAUSTED keys are revived here too (daily quota resets upstream);
    DISABLED keys are intentionally left alone — that's a manual decision.
    System-wide job — not scoped to one user.
    """
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
    """Runs periodically (e.g. every 15-30 min): probes EXHAUSTED keys to see
    if they've actually recovered (revoked key un-revoked, quota reset
    upstream out of band, etc.) and revives them if so.

    Deliberately scoped to EXHAUSTED only — ACTIVE keys don't need
    spending a request to prove they work, and COOLDOWN keys already have
    clear_expired_cooldowns handling their recovery on a known schedule.

    Walks every user's EXHAUSTED keys (system-wide job), but each probe is
    still issued through the owning user's own scoped repository lookup —
    check_key_health(key_id, user_id) — so it can never touch another
    account's key even by accident.
    """
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
