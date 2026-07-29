from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.keys.cache import KeyStatusCache
from app.keys.repository import APIKeyRepository
from app.keys.selector import KeySelector, RoundRobinSelector
from app.keys.service import KeyPoolService


def build_key_pool_service(
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    *,
    selector: KeySelector | None = None,
) -> KeyPoolService:
    repository = APIKeyRepository(session)
    cache = KeyStatusCache(redis, ttl_seconds=settings.KEY_STATUS_CACHE_TTL_SECONDS)
    return KeyPoolService(repository, cache, selector or RoundRobinSelector(redis))
