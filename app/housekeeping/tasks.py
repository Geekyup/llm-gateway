import logging
from contextlib import asynccontextmanager
from datetime import timedelta

from app.config import get_settings
from app.db.redis import get_redis
from app.db.session import get_sessionmaker
from app.keys.enums import KeyStatus
from app.keys.factory import build_key_pool_service
from app.monitoring.publisher import drain_event_queue_fully, purge_old_request_events

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _key_pool_service():
    session_factory = get_sessionmaker()
    settings = get_settings()
    redis = get_redis()

    async with session_factory() as session:
        yield build_key_pool_service(session, redis, settings)


async def clear_expired_cooldowns(ctx: dict) -> None:
    async with _key_pool_service() as service:
        revived_keys = await service.clear_expired_cooldowns()

    if revived_keys:
        logger.info("clear_expired_cooldowns: revived %d key(s)", len(revived_keys))


async def reset_daily_limits(ctx: dict) -> None:
    async with _key_pool_service() as service:
        reset_keys = await service.reset_daily_counters()

    logger.info("reset_daily_limits: reset %d key(s)", len(reset_keys))


async def health_check_exhausted_keys(ctx: dict) -> None:
    settings = get_settings()

    async with _key_pool_service() as service:
        exhausted = await service.list_all_keys_system_wide(status=KeyStatus.EXHAUSTED)
        results = await service.check_keys(
            exhausted,
            concurrency=settings.HOUSEKEEPING_HEALTH_CHECK_CONCURRENCY,
            delay_seconds=settings.HOUSEKEEPING_HEALTH_CHECK_DELAY_SECONDS,
        )

    if exhausted:
        revived = sum(1 for result in results if result.ok)
        logger.info("health_check_exhausted_keys: checked %d, revived %d", len(exhausted), revived)


async def flush_monitoring_events(ctx: dict) -> None:
    redis = get_redis()
    session_factory = get_sessionmaker()

    async with session_factory() as session:
        inserted = await drain_event_queue_fully(redis, session)

    if inserted:
        logger.info("flush_monitoring_events: inserted %d event(s)", inserted)


async def purge_old_monitoring_events(ctx: dict) -> None:
    settings = get_settings()
    retention = timedelta(days=settings.REQUEST_EVENTS_RETENTION_DAYS)

    session_factory = get_sessionmaker()

    async with session_factory() as session:
        deleted = await purge_old_request_events(session, older_than=retention)

    logger.info("purge_old_monitoring_events: deleted %d row(s) older than %s", deleted, retention)
