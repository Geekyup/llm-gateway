from typing import ClassVar

from arq import cron
from arq.connections import RedisSettings

from app.config import get_settings
from app.core.logging import configure_logging
from app.housekeeping.tasks import (
    clear_expired_cooldowns,
    health_check_exhausted_keys,
    purge_old_monitoring_events,
    reset_daily_limits,
)


async def startup(ctx: dict) -> None:
    settings = get_settings()
    configure_logging(debug=settings.DEBUG)


async def shutdown(ctx: dict) -> None:
    pass


def _redis_settings() -> RedisSettings:
    settings = get_settings()
    return RedisSettings.from_dsn(str(settings.REDIS_URL))


class WorkerSettings:
    redis_settings = _redis_settings()
    on_startup = startup
    on_shutdown = shutdown
    cron_jobs: ClassVar[list] = [
        cron(clear_expired_cooldowns, minute=set(range(0, 60, 5)), run_at_startup=True),
        cron(reset_daily_limits, hour=0, minute=0),
        cron(health_check_exhausted_keys, minute={0, 30}, run_at_startup=True),
        cron(purge_old_monitoring_events, hour=3, minute=0),
    ]