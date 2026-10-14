import time
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis

from app.api.deps import get_gateway_token_service
from app.config import Settings, get_settings
from app.core.metrics import RATE_LIMIT_REJECTIONS
from app.db.redis import get_redis
from app.tokens.service import GatewayTokenService

_bearer_scheme = HTTPBearer(auto_error=True)

_WINDOW_SECONDS = 60


async def _enforce_rate_limit(redis: Redis, user_id: int, limit: int) -> None:
    if limit <= 0:
        return

    now = int(time.time())
    window, elapsed_in_window = divmod(now, _WINDOW_SECONDS)
    counter_key = f"ratelimit:gateway:{user_id}:{window}"

    count = await redis.incr(counter_key)
    if count == 1:
        await redis.expire(counter_key, _WINDOW_SECONDS * 2)

    if count > limit:
        RATE_LIMIT_REJECTIONS.inc()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Gateway rate limit exceeded",
            headers={"Retry-After": str(_WINDOW_SECONDS - elapsed_in_window)},
        )


async def require_gateway_token(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)],
    token_service: Annotated[GatewayTokenService, Depends(get_gateway_token_service)],
    redis: Annotated[Redis, Depends(get_redis)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> int:
    user_id = await token_service.authenticate(credentials.credentials)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked gateway token"
        )
    await _enforce_rate_limit(redis, user_id, settings.GATEWAY_RATE_LIMIT_PER_MINUTE)
    return user_id
