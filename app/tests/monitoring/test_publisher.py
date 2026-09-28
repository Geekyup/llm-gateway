from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.monitoring.models import RequestEventRecord
from app.monitoring.publisher import (
    EVENTS_QUEUE_KEY,
    RequestEventPublisher,
    _day_window_utc,
    drain_event_queue,
    purge_old_request_events,
)
from app.monitoring.schemas import RequestEvent


def _event(
    user_id: int = 1,
    request_id: str = "req-1",
    attempt: int = 1,
    outcome: str = "success",
    key_id: int | None = 1,
    timestamp: datetime | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    provider: str = "gemini",
    model: str | None = None,
    latency_ms: int | None = 42,
) -> RequestEvent:
    return RequestEvent(
        user_id=user_id,
        request_id=request_id,
        attempt=attempt,
        timestamp=timestamp or datetime.now(UTC),
        provider=provider,
        path="v1beta/models/gemini-1.5-flash:generateContent",
        method="POST",
        key_id=key_id,
        key_label="k1",
        model=model,
        upstream_status=200,
        outcome=outcome,
        latency_ms=latency_ms,
        is_retry=attempt > 1,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )


async def _seed(db_session: AsyncSession, *events: RequestEvent) -> None:
    for event in events:
        db_session.add(
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
    await db_session.commit()


@pytest.mark.asyncio
async def test_publish_without_redis_does_not_raise():
    publisher = RequestEventPublisher()

    await publisher.publish(_event(request_id="no-redis"))


@pytest.mark.asyncio
async def test_publish_enqueues_to_redis(fake_redis):
    publisher = RequestEventPublisher(redis=fake_redis)

    await publisher.publish(_event(request_id="queued-1"))
    await publisher.publish(_event(request_id="queued-2"))

    raw = await fake_redis.lrange(EVENTS_QUEUE_KEY, 0, -1)
    assert len(raw) == 2
    assert RequestEvent.model_validate_json(raw[-1]).request_id == "queued-1"
    assert RequestEvent.model_validate_json(raw[0]).request_id == "queued-2"


@pytest.mark.asyncio
async def test_publish_failure_does_not_raise(fake_redis, monkeypatch):
    publisher = RequestEventPublisher(redis=fake_redis)

    def _broken_pipeline(transaction: bool = True):
        raise RuntimeError("redis is down")

    monkeypatch.setattr(fake_redis, "pipeline", _broken_pipeline)

    await publisher.publish(_event(request_id="redis-down"))


@pytest.mark.asyncio
async def test_drain_event_queue_persists_events_in_publish_order(
    db_session: AsyncSession, fake_redis
):
    publisher = RequestEventPublisher(redis=fake_redis)
    await publisher.publish(_event(request_id="first"))
    await publisher.publish(_event(request_id="second"))
    await publisher.publish(_event(request_id="third"))

    inserted = await drain_event_queue(fake_redis, db_session, batch_size=10)

    assert inserted == 3
    rows = (
        (await db_session.execute(select(RequestEventRecord).order_by(RequestEventRecord.id)))
        .scalars()
        .all()
    )
    assert [r.request_id for r in rows] == ["first", "second", "third"]


@pytest.mark.asyncio
async def test_drain_event_queue_respects_batch_size(db_session: AsyncSession, fake_redis):
    publisher = RequestEventPublisher(redis=fake_redis)
    for i in range(5):
        await publisher.publish(_event(request_id=f"r{i}"))

    first_batch = await drain_event_queue(fake_redis, db_session, batch_size=2)
    second_batch = await drain_event_queue(fake_redis, db_session, batch_size=10)

    assert first_batch == 2
    assert second_batch == 3


@pytest.mark.asyncio
async def test_drain_event_queue_returns_zero_when_empty(db_session: AsyncSession, fake_redis):
    inserted = await drain_event_queue(fake_redis, db_session)

    assert inserted == 0


@pytest.mark.asyncio
async def test_drain_event_queue_skips_malformed_entries(db_session: AsyncSession, fake_redis):
    publisher = RequestEventPublisher(redis=fake_redis)
    await publisher.publish(_event(request_id="valid"))
    await fake_redis.lpush(EVENTS_QUEUE_KEY, "not-valid-json{{{")

    inserted = await drain_event_queue(fake_redis, db_session, batch_size=10)

    assert inserted == 1
    rows = (await db_session.execute(select(RequestEventRecord))).scalars().all()
    assert [r.request_id for r in rows] == ["valid"]


@pytest.mark.asyncio
async def test_hourly_usage_buckets_by_hour_for_today(db_session: AsyncSession):
    publisher = RequestEventPublisher(session=db_session)
    now = datetime.now(UTC)
    nine_am = now.replace(hour=9, minute=15, second=0, microsecond=0)
    two_pm = now.replace(hour=14, minute=50, second=0, microsecond=0)

    await _seed(
        db_session,
        _event(request_id="a", timestamp=nine_am),
        _event(request_id="b", timestamp=nine_am + timedelta(minutes=5)),
        _event(request_id="c", timestamp=two_pm),
    )

    counts = await publisher.hourly_usage_for_key(1, key_id=1)

    assert len(counts) == 24
    assert counts[9] == 2
    assert counts[14] == 1
    assert sum(counts) == 3


@pytest.mark.asyncio
async def test_hourly_usage_ignores_other_keys_and_users(db_session: AsyncSession):
    publisher = RequestEventPublisher(session=db_session)
    now = datetime.now(UTC)

    await _seed(
        db_session,
        _event(request_id="mine", key_id=1, timestamp=now),
        _event(request_id="other-key", key_id=2, timestamp=now),
        _event(request_id="other-user", user_id=2, key_id=1, timestamp=now),
    )

    counts = await publisher.hourly_usage_for_key(1, key_id=1)

    assert sum(counts) == 1


@pytest.mark.asyncio
async def test_hourly_usage_excludes_events_from_previous_days(db_session: AsyncSession):
    publisher = RequestEventPublisher(session=db_session)
    yesterday = datetime.now(UTC) - timedelta(days=1)

    await _seed(db_session, _event(request_id="stale", timestamp=yesterday))

    counts = await publisher.hourly_usage_for_key(1, key_id=1)

    assert sum(counts) == 0


@pytest.mark.asyncio
async def test_hourly_usage_ignores_events_with_no_upstream_call(db_session: AsyncSession):
    publisher = RequestEventPublisher(session=db_session)
    now = datetime.now(UTC)

    await _seed(db_session, _event(request_id="dropped", outcome="no_keys", timestamp=now))

    counts = await publisher.hourly_usage_for_key(1, key_id=1)

    assert sum(counts) == 0


@pytest.mark.asyncio
async def test_hourly_token_usage_sums_by_hour_for_today(db_session: AsyncSession):
    publisher = RequestEventPublisher(session=db_session)
    now = datetime.now(UTC)
    nine_am = now.replace(hour=9, minute=0, second=0, microsecond=0)
    two_pm = now.replace(hour=14, minute=0, second=0, microsecond=0)

    await _seed(
        db_session,
        _event(
            request_id="a",
            timestamp=nine_am,
            prompt_tokens=100,
            completion_tokens=20,
            total_tokens=120,
        ),
        _event(
            request_id="b",
            timestamp=nine_am,
            prompt_tokens=50,
            completion_tokens=10,
            total_tokens=60,
        ),
        _event(
            request_id="c",
            timestamp=two_pm,
            prompt_tokens=200,
            completion_tokens=40,
            total_tokens=240,
        ),
    )

    triples = await publisher.hourly_token_usage_for_key(1, key_id=1)

    assert len(triples) == 24
    assert triples[9] == (150, 30, 180)
    assert triples[14] == (200, 40, 240)


@pytest.mark.asyncio
async def test_hourly_token_usage_skips_non_success_and_missing_tokens(db_session: AsyncSession):
    publisher = RequestEventPublisher(session=db_session)
    now = datetime.now(UTC)

    await _seed(
        db_session,
        _event(request_id="limited", outcome="rate_limited", timestamp=now),
        _event(request_id="legacy-success", outcome="success", timestamp=now),
    )

    triples = await publisher.hourly_token_usage_for_key(1, key_id=1)

    assert all(t == (0, 0, 0) for t in triples)


@pytest.mark.asyncio
async def test_hourly_token_usage_excludes_other_keys_and_stale_days(db_session: AsyncSession):
    publisher = RequestEventPublisher(session=db_session)
    now = datetime.now(UTC)
    yesterday = now - timedelta(days=1)

    await _seed(
        db_session,
        _event(
            request_id="mine",
            key_id=1,
            timestamp=now,
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
        ),
        _event(
            request_id="other-key",
            key_id=2,
            timestamp=now,
            prompt_tokens=999,
            completion_tokens=999,
            total_tokens=1998,
        ),
        _event(
            request_id="stale",
            key_id=1,
            timestamp=yesterday,
            prompt_tokens=999,
            completion_tokens=999,
            total_tokens=1998,
        ),
    )

    triples = await publisher.hourly_token_usage_for_key(1, key_id=1)

    assert sum(t[2] for t in triples) == 15


@pytest.mark.asyncio
async def test_purge_deletes_rows_older_than_cutoff(db_session: AsyncSession):
    now = datetime.now(UTC)
    old = now - timedelta(days=40)
    recent = now - timedelta(days=5)

    await _seed(
        db_session,
        _event(request_id="old", timestamp=old),
        _event(request_id="recent", timestamp=recent),
    )

    deleted = await purge_old_request_events(db_session, older_than=timedelta(days=30))

    assert deleted == 1
    remaining = (await db_session.execute(select(RequestEventRecord))).scalars().all()
    assert [r.request_id for r in remaining] == ["recent"]


@pytest.mark.asyncio
async def test_purge_returns_zero_when_nothing_to_delete(db_session: AsyncSession):
    await _seed(db_session, _event(request_id="fresh", timestamp=datetime.now(UTC)))

    deleted = await purge_old_request_events(db_session, older_than=timedelta(days=30))

    assert deleted == 0


def test_day_window_utc_returns_labels_oldest_first_inclusive_of_today():
    start, labels = _day_window_utc(7)

    today = datetime.now(UTC).date()
    assert len(labels) == 7
    assert labels[-1] == today.isoformat()
    assert labels[0] == (today - timedelta(days=6)).isoformat()
    assert start.date() == today - timedelta(days=6)


def test_day_window_utc_single_day_is_today_only():
    _, labels = _day_window_utc(1)

    assert labels == [datetime.now(UTC).date().isoformat()]


@pytest.mark.asyncio
async def test_activity_log_returns_entries_newest_first_with_model(db_session: AsyncSession):
    publisher = RequestEventPublisher(session=db_session)
    now = datetime.now(UTC)

    await _seed(
        db_session,
        _event(request_id="older", timestamp=now - timedelta(minutes=5), model="gemini-2.0-flash"),
        _event(request_id="newer", timestamp=now, model="gemini-2.5-pro"),
    )

    entries, total = await publisher.activity_log(1, "7d", page=1, page_size=50)

    assert total == 2
    assert [e.model for e in entries] == ["gemini-2.5-pro", "gemini-2.0-flash"]


@pytest.mark.asyncio
async def test_activity_log_filters_by_provider_and_outcome(db_session: AsyncSession):
    publisher = RequestEventPublisher(session=db_session)
    now = datetime.now(UTC)

    await _seed(
        db_session,
        _event(request_id="a", provider="gemini", outcome="success", timestamp=now),
        _event(request_id="b", provider="groq", outcome="success", timestamp=now),
        _event(request_id="c", provider="gemini", outcome="rate_limited", timestamp=now),
    )

    entries, total = await publisher.activity_log(1, "7d", provider="gemini")
    assert total == 2

    entries, total = await publisher.activity_log(1, "7d", provider="gemini", outcome="success")
    assert total == 1
    assert entries[0].provider == "gemini"
    assert entries[0].outcome == "success"


@pytest.mark.asyncio
async def test_activity_log_paginates(db_session: AsyncSession):
    publisher = RequestEventPublisher(session=db_session)
    now = datetime.now(UTC)

    await _seed(
        db_session,
        *[_event(request_id=f"r{i}", timestamp=now - timedelta(minutes=i)) for i in range(5)],
    )

    page1, total = await publisher.activity_log(1, "7d", page=1, page_size=2)
    page2, _ = await publisher.activity_log(1, "7d", page=2, page_size=2)

    assert total == 5
    assert len(page1) == 2
    assert len(page2) == 2
    assert {e.id for e in page1}.isdisjoint({e.id for e in page2})


@pytest.mark.asyncio
async def test_activity_log_excludes_events_outside_range_and_other_users(db_session: AsyncSession):
    publisher = RequestEventPublisher(session=db_session)
    now = datetime.now(UTC)

    await _seed(
        db_session,
        _event(request_id="mine", user_id=1, timestamp=now),
        _event(request_id="other-user", user_id=2, timestamp=now),
        _event(request_id="stale", user_id=1, timestamp=now - timedelta(days=10)),
    )

    entries, total = await publisher.activity_log(1, "7d")

    assert total == 1
    assert entries[0].id is not None


@pytest.mark.asyncio
async def test_daily_timeseries_buckets_success_and_rate_limited_by_day(db_session: AsyncSession):
    publisher = RequestEventPublisher(session=db_session)
    today = datetime.now(UTC)

    await _seed(
        db_session,
        _event(request_id="s1", outcome="success", timestamp=today),
        _event(request_id="s2", outcome="success", timestamp=today),
        _event(request_id="rl1", outcome="rate_limited", timestamp=today),
        _event(request_id="ex1", outcome="exhausted", timestamp=today),
    )

    buckets = await publisher.daily_timeseries(1, "7d")

    today_bucket = next(b for b in buckets if b.date == today.date().isoformat())
    assert today_bucket.success == 2
    assert today_bucket.rate_limited == 2
    assert today_bucket.error == 0


@pytest.mark.asyncio
async def test_daily_timeseries_excludes_no_keys_and_upstream_exhausted(db_session: AsyncSession):
    publisher = RequestEventPublisher(session=db_session)
    today = datetime.now(UTC)

    await _seed(
        db_session,
        _event(request_id="attempted", outcome="success", timestamp=today),
        _event(request_id="no-keys", outcome="no_keys", timestamp=today),
        _event(request_id="upstream-exhausted", outcome="upstream_exhausted", timestamp=today),
    )

    buckets = await publisher.daily_timeseries(1, "7d")

    total_in_timeseries = sum(b.success + b.rate_limited + b.error for b in buckets)
    assert total_in_timeseries == 1


@pytest.mark.asyncio
async def test_daily_timeseries_fills_days_with_no_events(db_session: AsyncSession):
    publisher = RequestEventPublisher(session=db_session)

    buckets = await publisher.daily_timeseries(1, "7d")

    assert len(buckets) == 7
    assert all(b.success == 0 and b.rate_limited == 0 and b.error == 0 for b in buckets)


@pytest.mark.asyncio
async def test_daily_timeseries_excludes_other_users(db_session: AsyncSession):
    publisher = RequestEventPublisher(session=db_session)
    today = datetime.now(UTC)

    await _seed(
        db_session, _event(request_id="theirs", user_id=2, outcome="success", timestamp=today)
    )

    buckets = await publisher.daily_timeseries(1, "7d")

    assert sum(b.success for b in buckets) == 0