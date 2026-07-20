import logging

from redis.asyncio import Redis

from llm_gateway.monitoring.schemas import RequestEvent

logger = logging.getLogger(__name__)

CHANNEL = "monitoring:requests"
HISTORY_KEY = "monitoring:requests:history"
HISTORY_MAX_LEN = 200


class RequestEventPublisher:
    """Fire-and-forget event bus for the live request monitor.

    Two Redis structures, deliberately simple:
    - Pub/Sub channel: fan-out to whatever admin dashboards are currently
      connected via SSE. Nobody listening -> message is just dropped.
    - Capped List: last HISTORY_MAX_LEN events, so a dashboard opened
      *after* traffic already happened isn't staring at a blank screen.

    Publishing must never break the actual proxy request — any Redis
    failure here is logged and swallowed, not raised.
    """

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def publish(self, event: RequestEvent) -> None:
        payload = event.model_dump_json()
        try:
            async with self._redis.pipeline(transaction=False) as pipe:
                pipe.publish(CHANNEL, payload)
                pipe.lpush(HISTORY_KEY, payload)
                pipe.ltrim(HISTORY_KEY, 0, HISTORY_MAX_LEN - 1)
                await pipe.execute()
        except Exception:  # noqa: BLE001 - monitoring must never break the gateway hot path
            logger.warning("failed to publish monitoring event request_id=%s", event.request_id, exc_info=True)

    async def recent(self, limit: int = 50) -> list[RequestEvent]:
        limit = min(limit, HISTORY_MAX_LEN)
        raw = await self._redis.lrange(HISTORY_KEY, 0, limit - 1)
        events = []
        for item in raw:
            try:
                events.append(RequestEvent.model_validate_json(item))
            except Exception:  # noqa: BLE001 - skip malformed/legacy entries, don't fail the whole read
                logger.warning("failed to parse monitoring history entry", exc_info=True)
        return events
