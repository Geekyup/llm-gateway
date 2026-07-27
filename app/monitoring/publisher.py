import logging
from datetime import UTC, datetime

from redis.asyncio import Redis

from app.monitoring.schemas import RequestEvent

logger = logging.getLogger(__name__)

CHANNEL_PREFIX = "monitoring:requests"
HISTORY_KEY_PREFIX = "monitoring:requests:history"
HISTORY_MAX_LEN = 200


def channel_for(user_id: int) -> str:
    return f"{CHANNEL_PREFIX}:{user_id}"


def _history_key(user_id: int) -> str:
    return f"{HISTORY_KEY_PREFIX}:{user_id}"


class RequestEventPublisher:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def publish(self, event: RequestEvent) -> None:
        payload = event.model_dump_json()
        try:
            async with self._redis.pipeline(transaction=False) as pipe:
                pipe.publish(channel_for(event.user_id), payload)
                pipe.lpush(_history_key(event.user_id), payload)
                pipe.ltrim(_history_key(event.user_id), 0, HISTORY_MAX_LEN - 1)
                results = await pipe.execute()
            logger.info(
                "monitoring publish: user_id=%s channel=%s subscribers_notified=%s",
                event.user_id, channel_for(event.user_id), results[0] if results else "?",
            )
        except Exception:
            logger.warning("failed to publish monitoring event request_id=%s", event.request_id, exc_info=True)

    async def recent(self, user_id: int, limit: int = 50) -> list[RequestEvent]:
        limit = min(limit, HISTORY_MAX_LEN)
        raw = await self._redis.lrange(_history_key(user_id), 0, limit - 1)
        events = []
        for item in raw:
            try:
                events.append(RequestEvent.model_validate_json(item))
            except Exception:
                logger.warning("failed to parse monitoring history entry", exc_info=True)
        return events

    async def hourly_usage_for_key(self, user_id: int, key_id: int) -> list[int]:
        counts = [0] * 24
        raw = await self._redis.lrange(_history_key(user_id), 0, HISTORY_MAX_LEN - 1)
        today = datetime.now(UTC).date()
        for item in raw:
            try:
                event = RequestEvent.model_validate_json(item)
            except Exception:
                logger.debug("skipping malformed history entry", exc_info=True)
                continue
            if event.key_id != key_id:
                continue
            if event.outcome not in ("success", "rate_limited", "exhausted"):
                continue
            ts = event.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            ts = ts.astimezone(UTC)
            if ts.date() != today:
                continue
            counts[ts.hour] += 1
        return counts

    async def hourly_token_usage_for_key(self, user_id: int, key_id: int) -> list[tuple[int, int, int]]:
        prompt = [0] * 24
        completion = [0] * 24
        total = [0] * 24
        raw = await self._redis.lrange(_history_key(user_id), 0, HISTORY_MAX_LEN - 1)
        today = datetime.now(UTC).date()
        for item in raw:
            try:
                event = RequestEvent.model_validate_json(item)
            except Exception:
                logger.debug("skipping malformed history entry", exc_info=True)
                continue
            if event.key_id != key_id or event.outcome != "success":
                continue
            if event.total_tokens is None:
                continue
            ts = event.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            ts = ts.astimezone(UTC)
            if ts.date() != today:
                continue
            h = ts.hour
            prompt[h] += event.prompt_tokens or 0
            completion[h] += event.completion_tokens or 0
            total[h] += event.total_tokens
        return list(zip(prompt, completion, total))
