from typing import ClassVar

from arq import cron
from arq.connections import RedisSettings

from app.config import get_settings
from app.core.logging import configure_logging
from app.housekeeping.tasks import (
    clear_expired_cooldowns,
    health_check_exhausted_keys,
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
        # Revive keys whose temporary cooldown window has passed.
        cron(clear_expired_cooldowns, minute=set(range(0, 60, 5)), run_at_startup=True),
        # Daily reset of requests_today / EXHAUSTED status at the top of the hour
        # configured in settings (default: hour boundary, minute 0).
        cron(reset_daily_limits, hour=0, minute=0),
        # Probe EXHAUSTED keys every 30 min in case they recovered upstream
        # (unrevoked, quota reset out of band) before the daily reset.
        cron(health_check_exhausted_keys, minute={0, 30}, run_at_startup=True),
    ]
