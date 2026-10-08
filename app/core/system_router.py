import asyncio
import logging
import secrets
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from redis.asyncio import Redis
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.metrics import EVENTS_QUEUE_LENGTH, KEYS
from app.db.redis import get_redis
from app.db.session import get_db
from app.keys.enums import KeyStatus, ProviderType
from app.keys.models import APIKey
from app.monitoring.publisher import EVENTS_QUEUE_KEY

logger = logging.getLogger(__name__)

router = APIRouter(tags=["meta"])


async def _probe(name: str, check: Callable[[], Awaitable[object]], timeout: float) -> str:
    try:
        await asyncio.wait_for(check(), timeout)
    except Exception as exc:
        logger.warning("readiness check failed", extra={"check": name, "error": type(exc).__name__})
        return f"failed: {type(exc).__name__}"
    return "ok"


async def refresh_gauges(session: AsyncSession, redis: Redis) -> None:
    try:
        rows = (
            await session.execute(
                select(APIKey.provider, APIKey.status, func.count()).group_by(APIKey.provider, APIKey.status)
            )
        ).all()
    except Exception:
        logger.warning("failed to refresh key gauges", exc_info=True)
        KEYS.clear()
    else:
        counts = {(provider.value, status.value): total for provider, status, total in rows}
        for provider in ProviderType:
            for status in KeyStatus:
                KEYS.labels(provider.value, status.value).set(counts.get((provider.value, status.value), 0))

    try:
        EVENTS_QUEUE_LENGTH.set(await redis.llen(EVENTS_QUEUE_KEY))
    except Exception:
        logger.warning("failed to read events queue length", exc_info=True)


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    timeout = settings.READINESS_TIMEOUT_SECONDS
    database, cache = await asyncio.gather(
        _probe("database", lambda: session.execute(text("SELECT 1")), timeout),
        _probe("redis", lambda: redis.ping(), timeout),
    )
    is_ready = database == "ok" and cache == "ok"
    return JSONResponse(
        status_code=200 if is_ready else 503,
        content={
            "status": "ready" if is_ready else "unavailable",
            "checks": {"database": database, "redis": cache},
        },
    )


@router.get("/metrics", include_in_schema=False)
async def metrics(
    request: Request,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> Response:
    expected = settings.METRICS_TOKEN
    if expected:
        scheme, _, supplied = request.headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not secrets.compare_digest(supplied.strip().encode(), expected.encode()):
            return Response(status_code=401, headers={"WWW-Authenticate": "Bearer"})

    await refresh_gauges(session, redis)
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
