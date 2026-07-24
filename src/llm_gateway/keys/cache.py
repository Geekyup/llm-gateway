import json

from redis.asyncio import Redis

from llm_gateway.keys.schemas import APIKeyDTO


class KeyStatusCache:
    """Caches the list of ACTIVE key metadata (id, label, counters, status)
    per provider so the hot request path doesn't hit Postgres on every
    single gateway call.

    IMPORTANT: DTOs stored here must NOT carry `decrypted_key`. Decryption
    happens exactly once, right before the upstream call, straight from a
    freshly-read ORM row — never cached, never logged. This cache exists
    purely to avoid a metadata SELECT, not to avoid the Fernet call (which
    is already fast) or to persist plaintext secrets in Redis.
    """

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
