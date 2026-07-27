from abc import ABC, abstractmethod

from redis.asyncio import Redis

from app.keys.schemas import APIKeyDTO


class KeySelector(ABC):
    @abstractmethod
    async def select(self, user_id: int, provider: str, candidates: list[APIKeyDTO]) -> APIKeyDTO | None:
        pass


class RoundRobinSelector(KeySelector):
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
