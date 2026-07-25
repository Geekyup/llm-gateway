from abc import ABC, abstractmethod

from redis.asyncio import Redis

from app.keys.schemas import APIKeyDTO


class KeySelector(ABC):
    """Strategy interface for picking one key out of a candidate list.

    Deliberately stateless from the caller's point of view — any state
    the strategy needs (like a round-robin cursor) is its own concern and
    must be shared across API replicas (i.e. live in Redis, not memory).
    """

    @abstractmethod
    async def select(self, user_id: int, provider: str, candidates: list[APIKeyDTO]) -> APIKeyDTO | None:
        """Return the next key to try, or None if candidates is empty."""


class RoundRobinSelector(KeySelector):
    """Cursor lives in Redis under `keyselector:cursor:{user_id}:{provider}`
    so that multiple API replicas rotate through the same sequence instead
    of each starting from index 0, and each user's rotation is independent.
    """

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    def _cursor_key(self, user_id: int, provider: str) -> str:
        return f"keyselector:cursor:{user_id}:{provider}"

    async def select(self, user_id: int, provider: str, candidates: list[APIKeyDTO]) -> APIKeyDTO | None:
        if not candidates:
            return None
        cursor = await self._redis.incr(self._cursor_key(user_id, provider))
        index = cursor % len(candidates)
        return candidates[index]
