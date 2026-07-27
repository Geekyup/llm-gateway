from functools import lru_cache

from redis.asyncio import ConnectionPool, Redis

from app.config import get_settings


@lru_cache
def get_redis_pool() -> ConnectionPool:
    settings = get_settings()
    return ConnectionPool.from_url(str(settings.REDIS_URL), decode_responses=True)


def get_redis() -> Redis:
    return Redis(connection_pool=get_redis_pool())
