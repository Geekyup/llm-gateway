from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.redis import get_redis
from app.db.session import get_db
from app.gateway.proxy_service import GatewayService
from app.keys.factory import build_key_pool_service
from app.keys.repository import APIKeyRepository
from app.keys.service import KeyPoolService
from app.monitoring.publisher import RequestEventPublisher
from app.tokens.repository import GatewayTokenRepository
from app.tokens.service import GatewayTokenService


def get_key_repository(session: Annotated[AsyncSession, Depends(get_db)]) -> APIKeyRepository:
    return APIKeyRepository(session)


def get_gateway_token_repository(session: Annotated[AsyncSession, Depends(get_db)]) -> GatewayTokenRepository:
    return GatewayTokenRepository(session)


def get_gateway_token_service(
    repository: Annotated[GatewayTokenRepository, Depends(get_gateway_token_repository)],
) -> GatewayTokenService:
    return GatewayTokenService(repository)


def get_key_pool_service(
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> KeyPoolService:
    return build_key_pool_service(session, redis, settings)


def get_event_publisher(
    redis: Annotated[Redis, Depends(get_redis)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RequestEventPublisher:
    return RequestEventPublisher(redis, session=session)


def get_gateway_service(
    key_pool: Annotated[KeyPoolService, Depends(get_key_pool_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    events: Annotated[RequestEventPublisher, Depends(get_event_publisher)],
) -> GatewayService:
    return GatewayService(key_pool, max_attempts=settings.GATEWAY_MAX_RETRY_ATTEMPTS, event_publisher=events)