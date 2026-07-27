import json

from redis.asyncio import Redis

from app.keys.schemas import APIKeyDTO


class KeyStatusCache:
    def __init__(self, redis: Redis, ttl_seconds: int) -> None:
        self._redis = redis
        self._ttl = ttl_seconds

    def _cache_key(self, user_id: int, provider: str) -> str:
        return f"keypool:active:{user_id}:{provider}"

    async def get_active(self, user_id: int, provider: str) -> list[APIKeyDTO] | None:
        raw = await self._redis.get(self._cache_key(user_id, provider))
        if raw is None:
            return None
        data = json.loads(raw)
        return [APIKeyDTO.model_validate(item) for item in data]

    async def set_active(self, user_id: int, provider: str, keys: list[APIKeyDTO]) -> None:
        payload = json.dumps([key.model_dump(mode="json") for key in keys])
        await self._redis.set(self._cache_key(user_id, provider), payload, ex=self._ttl)

    async def invalidate(self, user_id: int, provider: str) -> None:
        await self._redis.delete(self._cache_key(user_id, provider))
