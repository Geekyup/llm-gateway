import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from redis.asyncio import Redis
from sse_starlette.sse import EventSourceResponse

from llm_gateway.auth.deps import get_current_user
from llm_gateway.auth.models import User
from llm_gateway.db.redis import get_redis
from llm_gateway.monitoring.publisher import RequestEventPublisher, channel_for
from llm_gateway.monitoring.schemas import RequestEvent, RequestEventList

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/me/monitor", tags=["monitoring"])

_KEEPALIVE_SECONDS = 15.0


def get_event_publisher(redis: Annotated[Redis, Depends(get_redis)]) -> RequestEventPublisher:
    return RequestEventPublisher(redis)


@router.get("/recent", response_model=RequestEventList)
async def recent_events(
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    publisher: RequestEventPublisher = Depends(get_event_publisher),
) -> RequestEventList:
    """Snapshot of the last N proxied-request events for the caller only,
    newest first.

    Used to populate the dashboard immediately on load, before any new
    traffic arrives on the live stream below.
    """
    events = await publisher.recent(user.id, limit=limit)
    return RequestEventList(events=events)


@router.get("/stream")
async def stream_events(
    request: Request,
    user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
) -> EventSourceResponse:
    """Server-Sent Events stream of the caller's own request events as they happen.

    One Redis Pub/Sub subscription per connected client, scoped to that
    user's channel — nobody can ever subscribe to another user's traffic,
    since the channel name is derived from the authenticated JWT, not from
    anything the client supplies. Disconnects are detected via
    `request.is_disconnected()` so we don't leak subscriptions when a
    dashboard tab is closed.
    """

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

                try:
                    RequestEvent.model_validate_json(message["data"])
                except Exception:  # noqa: BLE001 - never let a malformed event kill the stream
                    logger.warning("dropping malformed monitoring event", exc_info=True)
                    continue

                yield {"event": "request", "data": message["data"]}
        finally:
            await pubsub.unsubscribe(channel_for(user.id))
            await pubsub.aclose()

    return EventSourceResponse(event_generator())
