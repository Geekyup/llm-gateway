import logging
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import case as sa_case
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.monitoring.models import RequestEventRecord
from app.monitoring.schemas import (
    ActivityLogEntry,
    ActivityRange,
    ActivitySummary,
    DailyOutcomeBucket,
    LatencyPercentileBucket,
    MonitorRange,
    RequestEvent,
    TimeseriesBucket,
    TokensByProviderBucket,
    TopModelEntry,
)

logger = logging.getLogger(__name__)

CHANNEL_PREFIX = "monitoring:requests"
HISTORY_KEY_PREFIX = "monitoring:requests:history"
HISTORY_MAX_LEN = 200

_RANGE_CONFIG: dict[MonitorRange, tuple[int, int]] = {
    "30m": (30 * 60, 2 * 60),
    "6h": (6 * 60 * 60, 15 * 60),
    "24h": (24 * 60 * 60, 60 * 60),
}

_ACTIVITY_RANGE_DAYS: dict[ActivityRange, int] = {
    "24h": 1,
    "7d": 7,
    "30d": 30,
}

_ATTEMPTED_OUTCOMES = ("success", "rate_limited", "exhausted")


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
                model=event.model,
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

    async def timeseries_for_user(self, user_id: int, range_: MonitorRange) -> list[TimeseriesBucket]:
        assert self._session is not None, "timeseries aggregation requires a DB session"

        window_seconds, bucket_seconds = _RANGE_CONFIG[range_]
        now = datetime.now(UTC)
        window_start = now - timedelta(seconds=window_seconds)

        bucket_expr = (
            func.floor(func.extract("epoch", RequestEventRecord.timestamp) / bucket_seconds) * bucket_seconds
        )

        stmt = (
            select(
                bucket_expr.label("bucket_ts"),
                RequestEventRecord.provider,
                func.count().label("count"),
                func.percentile_cont(0.5)
                .within_group(RequestEventRecord.latency_ms.asc())
                .label("p50"),
            )
            .where(
                RequestEventRecord.user_id == user_id,
                RequestEventRecord.outcome.in_(("success", "rate_limited", "exhausted")),
                RequestEventRecord.timestamp >= window_start,
            )
            .group_by("bucket_ts", RequestEventRecord.provider)
            .order_by("bucket_ts")
        )
        rows = await self._session.execute(stmt)

        by_bucket: dict[int, TimeseriesBucket] = {}
        p50_weighted: dict[int, float] = {}
        for bucket_ts, provider, count, p50 in rows:
            ts_ms = int(bucket_ts) * 1000
            bucket = by_bucket.setdefault(ts_ms, TimeseriesBucket(ts=ts_ms, count=0, p50=None, providers={}))
            bucket.count += count
            bucket.providers[provider] = count
            if p50 is not None:
                p50_weighted[ts_ms] = p50_weighted.get(ts_ms, 0.0) + float(p50) * count

        for ts_ms, bucket in by_bucket.items():
            if bucket.count > 0 and ts_ms in p50_weighted:
                bucket.p50 = round(p50_weighted[ts_ms] / bucket.count, 1)

        window_start_ts = int(window_start.timestamp() // bucket_seconds) * bucket_seconds
        bucket_count = window_seconds // bucket_seconds
        result: list[TimeseriesBucket] = []
        for i in range(bucket_count):
            ts_ms = (window_start_ts + i * bucket_seconds) * 1000
            result.append(by_bucket.get(ts_ms) or TimeseriesBucket(ts=ts_ms, count=0, p50=None, providers={}))
        return result

    async def activity_summary(self, user_id: int, range_: ActivityRange) -> ActivitySummary:
        assert self._session is not None, "activity aggregation requires a DB session"

        days = _ACTIVITY_RANGE_DAYS[range_]
        now = datetime.now(UTC)
        curr_start = now - timedelta(days=days)
        prev_start = now - timedelta(days=days * 2)

        curr = await self._window_stats(user_id, curr_start, now)
        prev = await self._window_stats(user_id, prev_start, curr_start)

        return ActivitySummary(
            total_requests=curr["total"],
            prev_total_requests=prev["total"],
            success_rate=curr["success_rate"],
            prev_success_rate=prev["success_rate"],
            latency_p50=curr["p50"],
            latency_p95=curr["p95"],
            prev_latency_p95=prev["p95"],
            total_tokens=curr["total_tokens"],
            prev_total_tokens=prev["total_tokens"],
        )

    async def _window_stats(self, user_id: int, start: datetime, end: datetime) -> dict:
        assert self._session is not None

        stmt = select(
            func.count().label("total"),
            func.sum(sa_case((RequestEventRecord.outcome == "success", 1), else_=0)).label("success"),
            func.percentile_cont(0.5)
            .within_group(RequestEventRecord.latency_ms.asc())
            .label("p50"),
            func.percentile_cont(0.95)
            .within_group(RequestEventRecord.latency_ms.asc())
            .label("p95"),
        ).where(
            RequestEventRecord.user_id == user_id,
            RequestEventRecord.outcome.in_(_ATTEMPTED_OUTCOMES),
            RequestEventRecord.timestamp >= start,
            RequestEventRecord.timestamp < end,
        )
        row = (await self._session.execute(stmt)).one()
        total = row.total or 0
        success = row.success or 0

        tokens_stmt = select(func.coalesce(func.sum(RequestEventRecord.total_tokens), 0)).where(
            RequestEventRecord.user_id == user_id,
            RequestEventRecord.outcome == "success",
            RequestEventRecord.timestamp >= start,
            RequestEventRecord.timestamp < end,
        )
        total_tokens = (await self._session.execute(tokens_stmt)).scalar_one()

        return {
            "total": total,
            "success_rate": round(100 * success / total, 1) if total else 0.0,
            "p50": round(float(row.p50), 1) if row.p50 is not None else None,
            "p95": round(float(row.p95), 1) if row.p95 is not None else None,
            "total_tokens": int(total_tokens),
        }

    async def daily_timeseries(self, user_id: int, range_: ActivityRange) -> list[DailyOutcomeBucket]:
        assert self._session is not None, "activity aggregation requires a DB session"

        days = _ACTIVITY_RANGE_DAYS[range_]
        start_date, day_labels = _day_window_utc(days)

        day_expr = func.date_trunc("day", RequestEventRecord.timestamp)
        stmt = (
            select(day_expr.label("day"), RequestEventRecord.outcome, func.count())
            .where(
                RequestEventRecord.user_id == user_id,
                RequestEventRecord.timestamp >= start_date,
            )
            .group_by("day", RequestEventRecord.outcome)
        )
        rows = await self._session.execute(stmt)

        by_day: dict[str, dict[str, int]] = {label: {"success": 0, "rate_limited": 0, "error": 0} for label in day_labels}
        for day, outcome, count in rows:
            label = day.date().isoformat()
            bucket = by_day.setdefault(label, {"success": 0, "rate_limited": 0, "error": 0})
            if outcome == "success":
                bucket["success"] += count
            elif outcome in ("rate_limited", "exhausted"):
                bucket["rate_limited"] += count
            else:
                bucket["error"] += count

        return [
            DailyOutcomeBucket(date=label, success=by_day[label]["success"],
                                rate_limited=by_day[label]["rate_limited"], error=by_day[label]["error"])
            for label in day_labels
        ]

    async def latency_percentiles_daily(self, user_id: int, range_: ActivityRange) -> list[LatencyPercentileBucket]:
        assert self._session is not None, "activity aggregation requires a DB session"

        days = _ACTIVITY_RANGE_DAYS[range_]
        start_date, day_labels = _day_window_utc(days)

        day_expr = func.date_trunc("day", RequestEventRecord.timestamp)
        stmt = (
            select(
                day_expr.label("day"),
                func.percentile_cont(0.5).within_group(RequestEventRecord.latency_ms.asc()).label("p50"),
                func.percentile_cont(0.95).within_group(RequestEventRecord.latency_ms.asc()).label("p95"),
                func.percentile_cont(0.99).within_group(RequestEventRecord.latency_ms.asc()).label("p99"),
            )
            .where(
                RequestEventRecord.user_id == user_id,
                RequestEventRecord.outcome.in_(_ATTEMPTED_OUTCOMES),
                RequestEventRecord.timestamp >= start_date,
            )
            .group_by("day")
        )
        rows = await self._session.execute(stmt)

        by_day: dict[str, LatencyPercentileBucket] = {
            label: LatencyPercentileBucket(date=label) for label in day_labels
        }
        for day, p50, p95, p99 in rows:
            label = day.date().isoformat()
            by_day[label] = LatencyPercentileBucket(
                date=label,
                p50=round(float(p50), 1) if p50 is not None else None,
                p95=round(float(p95), 1) if p95 is not None else None,
                p99=round(float(p99), 1) if p99 is not None else None,
            )

        return [by_day[label] for label in day_labels]

    async def tokens_by_provider_daily(self, user_id: int, range_: ActivityRange) -> list[TokensByProviderBucket]:
        assert self._session is not None, "activity aggregation requires a DB session"

        days = _ACTIVITY_RANGE_DAYS[range_]
        start_date, day_labels = _day_window_utc(days)

        day_expr = func.date_trunc("day", RequestEventRecord.timestamp)
        stmt = (
            select(day_expr.label("day"), RequestEventRecord.provider,
                   func.coalesce(func.sum(RequestEventRecord.total_tokens), 0))
            .where(
                RequestEventRecord.user_id == user_id,
                RequestEventRecord.outcome == "success",
                RequestEventRecord.timestamp >= start_date,
            )
            .group_by("day", RequestEventRecord.provider)
        )
        rows = await self._session.execute(stmt)

        by_day: dict[str, dict[str, int]] = {label: {} for label in day_labels}
        for day, provider, total in rows:
            label = day.date().isoformat()
            by_day.setdefault(label, {})[provider] = int(total)

        return [TokensByProviderBucket(date=label, providers=by_day[label]) for label in day_labels]

    async def top_models(self, user_id: int, range_: ActivityRange, limit: int = 10) -> list[TopModelEntry]:
        assert self._session is not None, "activity aggregation requires a DB session"

        days = _ACTIVITY_RANGE_DAYS[range_]
        start = datetime.now(UTC) - timedelta(days=days)

        stmt = (
            select(
                func.coalesce(RequestEventRecord.model, "unknown"),
                RequestEventRecord.provider,
                func.count(),
                func.coalesce(func.sum(RequestEventRecord.total_tokens), 0),
            )
            .where(
                RequestEventRecord.user_id == user_id,
                RequestEventRecord.outcome.in_(_ATTEMPTED_OUTCOMES),
                RequestEventRecord.timestamp >= start,
            )
            .group_by(RequestEventRecord.model, RequestEventRecord.provider)
            .order_by(func.count().desc())
            .limit(limit)
        )
        rows = await self._session.execute(stmt)
        return [
            TopModelEntry(model=model, provider=provider, requests=count, total_tokens=int(tokens))
            for model, provider, count, tokens in rows
        ]

    async def activity_log(
        self,
        user_id: int,
        range_: ActivityRange,
        page: int = 1,
        page_size: int = 50,
        provider: str | None = None,
        outcome: str | None = None,
    ) -> tuple[list[ActivityLogEntry], int]:
        assert self._session is not None, "activity log requires a DB session"

        days = _ACTIVITY_RANGE_DAYS[range_]
        start = datetime.now(UTC) - timedelta(days=days)

        filters = [RequestEventRecord.user_id == user_id, RequestEventRecord.timestamp >= start]
        if provider:
            filters.append(RequestEventRecord.provider == provider)
        if outcome:
            filters.append(RequestEventRecord.outcome == outcome)

        count_stmt = select(func.count()).select_from(RequestEventRecord).where(*filters)
        total = (await self._session.execute(count_stmt)).scalar_one()

        stmt = (
            select(RequestEventRecord)
            .where(*filters)
            .order_by(RequestEventRecord.timestamp.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self._session.execute(stmt)).scalars().all()

        entries = [
            ActivityLogEntry(
                id=row.id,
                timestamp=row.timestamp,
                provider=row.provider,
                model=row.model,
                key_label=row.key_label,
                outcome=row.outcome,
                latency_ms=row.latency_ms,
                total_tokens=row.total_tokens,
                upstream_status=row.upstream_status,
            )
            for row in rows
        ]
        return entries, int(total)


def _today_range_utc() -> tuple[datetime, datetime]:
    today = datetime.now(UTC).date()
    start = datetime(today.year, today.month, today.day, tzinfo=UTC)
    end = start + timedelta(days=1)
    return start, end


def _day_window_utc(days: int) -> tuple[datetime, list[str]]:
    """Return the UTC start of the window and ISO date labels, oldest first, inclusive of today."""
    today = datetime.now(UTC).date()
    start_date = today - timedelta(days=days - 1)
    start = datetime(start_date.year, start_date.month, start_date.day, tzinfo=UTC)
    labels = [(start_date + timedelta(days=i)).isoformat() for i in range(days)]
    return start, labels


async def purge_old_request_events(session: AsyncSession, older_than: timedelta) -> int:
    cutoff = datetime.now(UTC) - older_than
    result = await session.execute(delete(RequestEventRecord).where(RequestEventRecord.timestamp < cutoff))
    await session.commit()
    return result.rowcount or 0