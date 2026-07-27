import logging
from datetime import datetime, timezone

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
    """Fire-and-forget event bus for the live request monitor.

    Two Redis structures per user, deliberately simple:
    - Pub/Sub channel (monitoring:requests:{user_id}): fan-out to whatever
      dashboards that user currently has connected via SSE. Nobody
      listening -> message is just dropped. A user can never subscribe to
      another user's channel because the channel name is derived from the
      authenticated caller, not from anything client-supplied.
    - Capped List (monitoring:requests:history:{user_id}): last
      HISTORY_MAX_LEN events for that user, so a dashboard opened *after*
      traffic already happened isn't staring at a blank screen.

    Publishing must never break the actual proxy request — any Redis
    failure here is logged and swallowed, not raised.
    """

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
        except Exception:  # noqa: BLE001 - monitoring must never break the gateway hot path
            logger.warning("failed to publish monitoring event request_id=%s", event.request_id, exc_info=True)

    async def recent(self, user_id: int, limit: int = 50) -> list[RequestEvent]:
        limit = min(limit, HISTORY_MAX_LEN)
        raw = await self._redis.lrange(_history_key(user_id), 0, limit - 1)
        events = []
        for item in raw:
            try:
                events.append(RequestEvent.model_validate_json(item))
            except Exception:  # noqa: BLE001 - skip malformed/legacy entries, don't fail the whole read
                logger.warning("failed to parse monitoring history entry", exc_info=True)
        return events

    async def hourly_usage_for_key(self, user_id: int, key_id: int) -> list[int]:
        """Real per-hour request counts for one key, for the current UTC day.

        Built from the same capped history list the live monitor reads —
        no separate storage, so this is only as deep as HISTORY_MAX_LEN
        events for the *whole account* (all keys combined). For a busy
        account that can mean the earliest hours of a heavy day have
        already scrolled out of the window; there's no persistent request
        log to fall back on, so this is the best available signal without
        adding a database table.

        Only successful upstream calls count as "usage" here (skips
        no_keys/error attempts that never reached the provider).
        """
        counts = [0] * 24
        raw = await self._redis.lrange(_history_key(user_id), 0, HISTORY_MAX_LEN - 1)
        today = datetime.now(timezone.utc).date()
        for item in raw:
            try:
                event = RequestEvent.model_validate_json(item)
            except Exception:  # noqa: BLE001 - skip malformed/legacy entries
                continue
            if event.key_id != key_id:
                continue
            if event.outcome not in ("success", "rate_limited", "exhausted"):
                continue
            ts = event.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            ts = ts.astimezone(timezone.utc)
            if ts.date() != today:
                continue
            counts[ts.hour] += 1
        return counts

    async def hourly_token_usage_for_key(self, user_id: int, key_id: int) -> list[tuple[int, int, int]]:
        """Real per-hour token counts (prompt, completion, total) for one
        key, for the current UTC day.

        Same Redis-history source and same coverage caveat as
        hourly_usage_for_key. Only "success" events carry usageMetadata
        (rate_limited/exhausted attempts never reached generation, so
        there's nothing to count) — events missing token fields (e.g.
        published before this feature existed) are skipped.
        """
        prompt = [0] * 24
        completion = [0] * 24
        total = [0] * 24
        raw = await self._redis.lrange(_history_key(user_id), 0, HISTORY_MAX_LEN - 1)
        today = datetime.now(timezone.utc).date()
        for item in raw:
            try:
                event = RequestEvent.model_validate_json(item)
            except Exception:  # noqa: BLE001 - skip malformed/legacy entries
                continue
            if event.key_id != key_id or event.outcome != "success":
                continue
            if event.total_tokens is None:
                continue
            ts = event.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            ts = ts.astimezone(timezone.utc)
            if ts.date() != today:
                continue
            h = ts.hour
            prompt[h] += event.prompt_tokens or 0
            completion[h] += event.completion_tokens or 0
            total[h] += event.total_tokens
        return list(zip(prompt, completion, total))
