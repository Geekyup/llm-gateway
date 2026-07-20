from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from llm_gateway.config import Settings, get_settings
from llm_gateway.db.redis import get_redis
from llm_gateway.db.session import get_db
from llm_gateway.gateway.proxy_service import GatewayService
from llm_gateway.keys.cache import KeyStatusCache
from llm_gateway.keys.repository import APIKeyRepository
from llm_gateway.keys.selector import KeySelector, RoundRobinSelector
from llm_gateway.keys.service import KeyPoolService
from llm_gateway.monitoring.publisher import RequestEventPublisher


def get_key_repository(session: Annotated[AsyncSession, Depends(get_db)]) -> APIKeyRepository:
    return APIKeyRepository(session)


def get_key_cache(
    redis: Annotated[Redis, Depends(get_redis)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> KeyStatusCache:
    return KeyStatusCache(redis, ttl_seconds=settings.KEY_STATUS_CACHE_TTL_SECONDS)


def get_key_selector(redis: Annotated[Redis, Depends(get_redis)]) -> KeySelector:
    return RoundRobinSelector(redis)


def get_key_pool_service(
    repository: Annotated[APIKeyRepository, Depends(get_key_repository)],
    cache: Annotated[KeyStatusCache, Depends(get_key_cache)],
    selector: Annotated[KeySelector, Depends(get_key_selector)],
) -> KeyPoolService:
    return KeyPoolService(repository, cache, selector)


def get_event_publisher(redis: Annotated[Redis, Depends(get_redis)]) -> RequestEventPublisher:
    return RequestEventPublisher(redis)


def get_gateway_service(
    key_pool: Annotated[KeyPoolService, Depends(get_key_pool_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    events: Annotated[RequestEventPublisher, Depends(get_event_publisher)],
) -> GatewayService:
    return GatewayService(key_pool, max_attempts=settings.GATEWAY_MAX_RETRY_ATTEMPTS, event_publisher=events)
