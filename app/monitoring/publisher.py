import logging
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.monitoring.models import RequestEventRecord
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
    def __init__(self, redis: Redis, session: AsyncSession | None = None) -> None:
        self._redis = redis
        self._session = session

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

        if self._session is not None:
            try:
                await self._persist(event)
            except Exception:
                logger.warning(
                    "failed to persist monitoring event request_id=%s", event.request_id, exc_info=True
                )

    async def _persist(self, event: RequestEvent) -> None:
        assert self._session is not None
        self._session.add(
            RequestEventRecord(
                user_id=event.user_id,
                key_id=event.key_id,
                request_id=event.request_id,
                attempt=event.attempt,
                timestamp=event.timestamp,
                provider=event.provider,
                path=event.path,
                method=event.method,
                key_label=event.key_label,
                upstream_status=event.upstream_status,
                outcome=event.outcome,
                latency_ms=event.latency_ms,
                is_retry=event.is_retry,
                error_detail=event.error_detail,
                prompt_tokens=event.prompt_tokens,
                completion_tokens=event.completion_tokens,
                total_tokens=event.total_tokens,
            )
        )
        await self._session.commit()

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
        assert self._session is not None, "hourly aggregation requires a DB session"
        counts = [0] * 24
        start, end = _today_range_utc()
        stmt = (
            select(func.extract("hour", RequestEventRecord.timestamp), func.count())
            .where(
                RequestEventRecord.user_id == user_id,
                RequestEventRecord.key_id == key_id,
                RequestEventRecord.outcome.in_(("success", "rate_limited", "exhausted")),
                RequestEventRecord.timestamp >= start,
                RequestEventRecord.timestamp < end,
            )
            .group_by(func.extract("hour", RequestEventRecord.timestamp))
        )
        rows = await self._session.execute(stmt)
        for hour, count in rows:
            counts[int(hour)] = count
        return counts

    async def hourly_token_usage_for_key(self, user_id: int, key_id: int) -> list[tuple[int, int, int]]:
        assert self._session is not None, "hourly aggregation requires a DB session"
        prompt = [0] * 24
        completion = [0] * 24
        total = [0] * 24
        start, end = _today_range_utc()
        stmt = (
            select(
                func.extract("hour", RequestEventRecord.timestamp),
                func.coalesce(func.sum(RequestEventRecord.prompt_tokens), 0),
                func.coalesce(func.sum(RequestEventRecord.completion_tokens), 0),
                func.coalesce(func.sum(RequestEventRecord.total_tokens), 0),
            )
            .where(
                RequestEventRecord.user_id == user_id,
                RequestEventRecord.key_id == key_id,
                RequestEventRecord.outcome == "success",
                RequestEventRecord.total_tokens.is_not(None),
                RequestEventRecord.timestamp >= start,
                RequestEventRecord.timestamp < end,
            )
            .group_by(func.extract("hour", RequestEventRecord.timestamp))
        )
        rows = await self._session.execute(stmt)
        for hour, p, c, t in rows:
            h = int(hour)
            prompt[h] = int(p)
            completion[h] = int(c)
            total[h] = int(t)
        return list(zip(prompt, completion, total))


def _today_range_utc() -> tuple[datetime, datetime]:
    today = datetime.now(UTC).date()
    start = datetime(today.year, today.month, today.day, tzinfo=UTC)
    end = start + timedelta(days=1)
    return start, end


async def purge_old_request_events(session: AsyncSession, older_than: timedelta) -> int:
    cutoff = datetime.now(UTC) - older_than
    result = await session.execute(delete(RequestEventRecord).where(RequestEventRecord.timestamp < cutoff))
    await session.commit()
    return result.rowcount or 0