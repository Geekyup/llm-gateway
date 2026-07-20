from datetime import datetime, timezone

import pytest

from llm_gateway.monitoring.publisher import HISTORY_MAX_LEN, RequestEventPublisher
from llm_gateway.monitoring.schemas import RequestEvent


def _event(request_id: str = "req-1", attempt: int = 1, outcome: str = "success") -> RequestEvent:
    return RequestEvent(
        request_id=request_id,
        attempt=attempt,
        timestamp=datetime.now(timezone.utc),
        provider="gemini",
        path="v1beta/models/gemini-1.5-flash:generateContent",
        method="POST",
        key_id=1,
        key_label="k1",
        upstream_status=200,
        outcome=outcome,
        latency_ms=42,
        is_retry=attempt > 1,
    )


@pytest.mark.asyncio
async def test_publish_fans_out_to_pubsub_channel(fake_redis):
    publisher = RequestEventPublisher(fake_redis)
    event = _event()

    await publisher.publish(event)

    assert len(fake_redis.published) == 1
    channel, payload = fake_redis.published[0]
    assert channel == "monitoring:requests"
    assert RequestEvent.model_validate_json(payload) == event


@pytest.mark.asyncio
async def test_recent_returns_events_newest_first(fake_redis):
    publisher = RequestEventPublisher(fake_redis)
    first = _event(request_id="req-1")
    second = _event(request_id="req-2")

    await publisher.publish(first)
    await publisher.publish(second)

    events = await publisher.recent(limit=10)

    assert [e.request_id for e in events] == ["req-2", "req-1"]


@pytest.mark.asyncio
async def test_recent_respects_limit(fake_redis):
    publisher = RequestEventPublisher(fake_redis)
    for i in range(5):
        await publisher.publish(_event(request_id=f"req-{i}"))

    events = await publisher.recent(limit=2)

    assert len(events) == 2
    # Newest first: req-4 published last.
    assert events[0].request_id == "req-4"


@pytest.mark.asyncio
async def test_history_capped_at_max_len(fake_redis):
    publisher = RequestEventPublisher(fake_redis)
    for i in range(HISTORY_MAX_LEN + 10):
        await publisher.publish(_event(request_id=f"req-{i}"))

    events = await publisher.recent(limit=HISTORY_MAX_LEN + 10)

    assert len(events) == HISTORY_MAX_LEN


@pytest.mark.asyncio
async def test_publish_failure_is_swallowed_not_raised(fake_redis, monkeypatch):
    publisher = RequestEventPublisher(fake_redis)

    def _broken_pipeline(transaction: bool = True):
        raise RuntimeError("redis is down")

    monkeypatch.setattr(fake_redis, "pipeline", _broken_pipeline)

    # Must not raise — monitoring is best-effort and should never break the
    # actual gateway request path.
    await publisher.publish(_event())
