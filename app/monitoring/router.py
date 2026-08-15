import logging

from fastapi import APIRouter, Depends, Query, Request
from redis.asyncio import Redis
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_event_publisher
from app.auth.deps import get_current_user
from app.auth.models import User
from app.db.redis import get_redis
from app.monitoring.publisher import RequestEventPublisher, channel_for
from app.monitoring.schemas import MonitorRange, RequestEvent, RequestEventList, TimeseriesResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/me/monitor", tags=["monitoring"])

_KEEPALIVE_SECONDS = 15.0


@router.get("/recent", response_model=RequestEventList)
async def recent_events(
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    publisher: RequestEventPublisher = Depends(get_event_publisher),
) -> RequestEventList:
    events = await publisher.recent(user.id, limit=limit)
    return RequestEventList(events=events)


@router.get("/timeseries", response_model=TimeseriesResponse)
async def timeseries(
    range: MonitorRange = Query(default="30m"),
    user: User = Depends(get_current_user),
    publisher: RequestEventPublisher = Depends(get_event_publisher),
) -> TimeseriesResponse:
    buckets = await publisher.timeseries_for_user(user.id, range)
    return TimeseriesResponse(range=range, buckets=buckets)


@router.get("/stream")
async def stream_events(
    request: Request,
    user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
) -> EventSourceResponse:
    async def event_generator():
        pubsub = redis.pubsub()
        await pubsub.subscribe(channel_for(user.id))
        try:
            while True:
                if await request.is_disconnected():
                    break

                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=_KEEPALIVE_SECONDS)
                if message is None:
                    yield {"event": "ping", "data": ""}
                    continue

                logger.info("monitoring stream: received message for user_id=%s", user.id)

                try:
                    RequestEvent.model_validate_json(message["data"])
                except Exception:
                    logger.warning("dropping malformed monitoring event", exc_info=True)
                    continue

                yield {"event": "request", "data": message["data"]}
        finally:
            await pubsub.unsubscribe(channel_for(user.id))
            await pubsub.aclose()

    return EventSourceResponse(
        event_generator(),
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )