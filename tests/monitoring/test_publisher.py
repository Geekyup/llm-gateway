from datetime import datetime, timedelta, timezone

import pytest

from app.monitoring.publisher import HISTORY_MAX_LEN, RequestEventPublisher, channel_for
from app.monitoring.schemas import RequestEvent


def _event(
    user_id: int = 1,
    request_id: str = "req-1",
    attempt: int = 1,
    outcome: str = "success",
    key_id: int | None = 1,
    timestamp: datetime | None = None,
) -> RequestEvent:
    return RequestEvent(
        user_id=user_id,
        request_id=request_id,
        attempt=attempt,
        timestamp=timestamp or datetime.now(timezone.utc),
        provider="gemini",
        path="v1beta/models/gemini-1.5-flash:generateContent",
        method="POST",
        key_id=key_id,
        key_label="k1",
        upstream_status=200,
        outcome=outcome,
        latency_ms=42,
        is_retry=attempt > 1,
    )


@pytest.mark.asyncio
async def test_publish_fans_out_to_pubsub_channel(fake_redis):
    publisher = RequestEventPublisher(fake_redis)
    event = _event(user_id=42)

    await publisher.publish(event)

    assert len(fake_redis.published) == 1
    channel, payload = fake_redis.published[0]
    assert channel == channel_for(42)
    assert RequestEvent.model_validate_json(payload) == event


@pytest.mark.asyncio
async def test_recent_returns_events_newest_first(fake_redis):
    publisher = RequestEventPublisher(fake_redis)
    first = _event(request_id="req-1")
    second = _event(request_id="req-2")

    await publisher.publish(first)
    await publisher.publish(second)

    events = await publisher.recent(1, limit=10)

    assert [e.request_id for e in events] == ["req-2", "req-1"]


@pytest.mark.asyncio
async def test_recent_respects_limit(fake_redis):
    publisher = RequestEventPublisher(fake_redis)
    for i in range(5):
        await publisher.publish(_event(request_id=f"req-{i}"))

    events = await publisher.recent(1, limit=2)

    assert len(events) == 2
    # Newest first: req-4 published last.
    assert events[0].request_id == "req-4"


@pytest.mark.asyncio
async def test_history_capped_at_max_len(fake_redis):
    publisher = RequestEventPublisher(fake_redis)
    for i in range(HISTORY_MAX_LEN + 10):
        await publisher.publish(_event(request_id=f"req-{i}"))

    events = await publisher.recent(1, limit=HISTORY_MAX_LEN + 10)

    assert len(events) == HISTORY_MAX_LEN


@pytest.mark.asyncio
async def test_events_isolated_per_user(fake_redis):
    """Two users' event histories and channels must never mix."""
    publisher = RequestEventPublisher(fake_redis)
    await publisher.publish(_event(user_id=1, request_id="mine"))
    await publisher.publish(_event(user_id=2, request_id="theirs"))

    user1_events = await publisher.recent(1, limit=10)
    user2_events = await publisher.recent(2, limit=10)

    assert [e.request_id for e in user1_events] == ["mine"]
    assert [e.request_id for e in user2_events] == ["theirs"]

    channels = [c for c, _ in fake_redis.published]
    assert channel_for(1) in channels
    assert channel_for(2) in channels
    assert channel_for(1) != channel_for(2)


@pytest.mark.asyncio
async def test_publish_failure_is_swallowed_not_raised(fake_redis, monkeypatch):
    publisher = RequestEventPublisher(fake_redis)

    def _broken_pipeline(transaction: bool = True):
        raise RuntimeError("redis is down")

    monkeypatch.setattr(fake_redis, "pipeline", _broken_pipeline)

    # Must not raise — monitoring is best-effort and should never break the
    # actual gateway request path.
    await publisher.publish(_event())


@pytest.mark.asyncio
async def test_hourly_usage_buckets_by_hour_for_today(fake_redis):
    publisher = RequestEventPublisher(fake_redis)
    now = datetime.now(timezone.utc)
    nine_am = now.replace(hour=9, minute=15, second=0, microsecond=0)
    two_pm = now.replace(hour=14, minute=50, second=0, microsecond=0)

    await publisher.publish(_event(request_id="a", timestamp=nine_am))
    await publisher.publish(_event(request_id="b", timestamp=nine_am + timedelta(minutes=5)))
    await publisher.publish(_event(request_id="c", timestamp=two_pm))

    counts = await publisher.hourly_usage_for_key(1, key_id=1)

    assert len(counts) == 24
    assert counts[9] == 2
    assert counts[14] == 1
    assert sum(counts) == 3


@pytest.mark.asyncio
async def test_hourly_usage_ignores_other_keys_and_users(fake_redis):
    publisher = RequestEventPublisher(fake_redis)
    now = datetime.now(timezone.utc)

    await publisher.publish(_event(request_id="mine", key_id=1, timestamp=now))
    await publisher.publish(_event(request_id="other-key", key_id=2, timestamp=now))
    await publisher.publish(_event(request_id="other-user", user_id=2, key_id=1, timestamp=now))

    counts = await publisher.hourly_usage_for_key(1, key_id=1)

    assert sum(counts) == 1


@pytest.mark.asyncio
async def test_hourly_usage_excludes_events_from_previous_days(fake_redis):
    publisher = RequestEventPublisher(fake_redis)
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)

    await publisher.publish(_event(request_id="stale", timestamp=yesterday))

    counts = await publisher.hourly_usage_for_key(1, key_id=1)

    assert sum(counts) == 0


@pytest.mark.asyncio
async def test_hourly_usage_ignores_events_with_no_upstream_call(fake_redis):
    publisher = RequestEventPublisher(fake_redis)
    now = datetime.now(timezone.utc)

    await publisher.publish(_event(request_id="dropped", outcome="no_keys", timestamp=now))

    counts = await publisher.hourly_usage_for_key(1, key_id=1)

    assert sum(counts) == 0
