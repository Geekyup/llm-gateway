import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from pydantic import BaseModel
from redis.asyncio import Redis

from app.core.metrics import ACTIVITY_CACHE

logger = logging.getLogger(__name__)

ModelT = TypeVar("ModelT", bound=BaseModel)

_KEY_PREFIX = "activity:v1"


class ActivityCache:
    def __init__(self, redis: Redis, ttl_seconds: int) -> None:
        self._redis = redis
        self._ttl_seconds = ttl_seconds

    async def get_or_load(
        self,
        *,
        user_id: int,
        endpoint: str,
        params: str,
        model: type[ModelT],
        loader: Callable[[], Awaitable[ModelT]],
    ) -> ModelT:
        if self._ttl_seconds <= 0:
            return await loader()

        key = f"{_KEY_PREFIX}:{user_id}:{endpoint}:{params}"
        try:
            cached = await self._redis.get(key)
        except Exception:
            logger.warning("activity cache read failed", exc_info=True)
            cached = None

        if cached is not None:
            try:
                value = model.model_validate_json(cached)
            except ValueError:
                logger.warning("activity cache entry is invalid", extra={"cache_key": key})
            else:
                ACTIVITY_CACHE.labels(endpoint, "hit").inc()
                return value

        ACTIVITY_CACHE.labels(endpoint, "miss").inc()
        value = await loader()
        try:
            await self._redis.set(key, value.model_dump_json(), ex=self._ttl_seconds)
        except Exception:
            logger.warning("activity cache write failed", exc_info=True)
        return value
