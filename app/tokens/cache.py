import logging

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class TokenAuthCache:
    def __init__(self, redis: Redis, ttl_seconds: int) -> None:
        self._redis = redis
        self._ttl = ttl_seconds

    @staticmethod
    def _cache_key(token_hash: str) -> str:
        return f"gwtoken:auth:{token_hash}"

    async def get(self, token_hash: str) -> int | None:
        try:
            raw = await self._redis.get(self._cache_key(token_hash))
        except Exception:
            logger.warning("token auth cache read failed", exc_info=True)
            return None
        return int(raw) if raw is not None else None

    async def set(self, token_hash: str, user_id: int) -> None:
        try:
            await self._redis.set(self._cache_key(token_hash), str(user_id), ex=self._ttl)
        except Exception:
            logger.warning("token auth cache write failed", exc_info=True)

    async def delete(self, token_hash: str) -> None:
        try:
            await self._redis.delete(self._cache_key(token_hash))
        except Exception:
            logger.warning("token auth cache invalidation failed", exc_info=True)
