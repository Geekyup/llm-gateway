import logging

from app.config import get_settings
from app.db.redis import get_redis
from app.db.session import get_sessionmaker
from app.keys.enums import KeyStatus
from app.keys.factory import build_key_pool_service

logger = logging.getLogger(__name__)


async def clear_expired_cooldowns(ctx: dict) -> None:
    session_factory = get_sessionmaker()
    settings = get_settings()
    redis = get_redis()

    async with session_factory() as session:
        service = build_key_pool_service(session, redis, settings)
        revived_keys = await service.clear_expired_cooldowns()

    if revived_keys:
        logger.info("clear_expired_cooldowns: revived %d key(s)", len(revived_keys))


async def reset_daily_limits(ctx: dict) -> None:
    session_factory = get_sessionmaker()
    settings = get_settings()
    redis = get_redis()

    async with session_factory() as session:
        service = build_key_pool_service(session, redis, settings)
        reset_keys = await service.reset_daily_counters()

    logger.info("reset_daily_limits: reset %d key(s)", len(reset_keys))


async def health_check_exhausted_keys(ctx: dict) -> None:
    session_factory = get_sessionmaker()
    settings = get_settings()
    redis = get_redis()

    async with session_factory() as session:
        service = build_key_pool_service(session, redis, settings)

        all_keys = await service._repo.list_all_system_wide()
        exhausted = [k for k in all_keys if k.status == KeyStatus.EXHAUSTED]
        revived = 0
        for key in exhausted:
            result = await service.check_key_health(key.id, key.user_id)
            if result.ok:
                revived += 1

    if exhausted:
        logger.info("health_check_exhausted_keys: checked %d, revived %d", len(exhausted), revived)
