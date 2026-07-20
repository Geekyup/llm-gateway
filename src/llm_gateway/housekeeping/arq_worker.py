from arq import cron
from arq.connections import RedisSettings

from llm_gateway.config import get_settings
from llm_gateway.core.logging import configure_logging
from llm_gateway.housekeeping.tasks import clear_expired_cooldowns, reset_daily_limits


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
    cron_jobs = [
        # Revive keys whose temporary cooldown window has passed.
        cron(clear_expired_cooldowns, minute=set(range(0, 60, 5)), run_at_startup=True),
        # Daily reset of requests_today / EXHAUSTED status at the top of the hour
        # configured in settings (default: hour boundary, minute 0).
        cron(reset_daily_limits, hour=0, minute=0),
    ]
