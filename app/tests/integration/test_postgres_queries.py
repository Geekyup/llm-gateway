from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, func, select

from app.auth.models import User
from app.keys.enums import KeyStatus, ProviderType
from app.keys.models import APIKey
from app.monitoring.models import RequestEventRecord
from app.monitoring.publisher import RequestEventPublisher

pytestmark = pytest.mark.integration


async def _seed_latencies(db_session, user_id: int, latencies: list[int], outcome: str = "success"):
    now = datetime.now(UTC)
    for index, latency in enumerate(latencies):
        db_session.add(
            RequestEventRecord(
                user_id=user_id,
                key_id=None,
                request_id=f"req-{index}",
                attempt=1,
                timestamp=now,
                provider="gemini",
                path="v1beta/models/x:generateContent",
                method="POST",
                key_label="k",
                model=None,
                upstream_status=200,
                outcome=outcome,
                latency_ms=latency,
                is_retry=False,
            )
        )
    await db_session.commit()


async def test_activity_summary_computes_percentiles_with_postgres(db_session, test_user):
    await _seed_latencies(db_session, test_user.id, [100, 200, 300, 400, 500])

    summary = await RequestEventPublisher(session=db_session).activity_summary(test_user.id, "7d")

    assert summary.total_requests == 5
    assert summary.success_rate == 100.0
    assert summary.latency_p50 == 300.0
    assert summary.latency_p95 == 480.0


async def test_daily_latency_percentiles_use_continuous_interpolation(db_session, test_user):
    await _seed_latencies(db_session, test_user.id, [100, 200, 300, 400, 500])

    buckets = await RequestEventPublisher(session=db_session).latency_percentiles_daily(
        test_user.id, "7d"
    )

    today = buckets[-1]
    assert (today.p50, today.p95, today.p99) == (300.0, 480.0, 496.0)
    assert all(b.p50 is None for b in buckets[:-1])


async def test_percentiles_ignore_outcomes_that_never_reached_upstream(db_session, test_user):
    await _seed_latencies(db_session, test_user.id, [100, 200])
    await _seed_latencies(db_session, test_user.id, [9000], outcome="no_keys")

    summary = await RequestEventPublisher(session=db_session).activity_summary(test_user.id, "7d")

    assert summary.total_requests == 2
    assert summary.latency_p95 == 195.0


async def test_foreign_keys_are_enforced_and_cascade_on_user_delete(db_session, test_user):
    key = APIKey(
        user_id=test_user.id,
        label="k",
        provider=ProviderType.GEMINI,
        key_encrypted="c",
        daily_limit=10,
        status=KeyStatus.ACTIVE,
    )
    db_session.add(key)
    await db_session.commit()
    await _seed_latencies(db_session, test_user.id, [100])

    await db_session.execute(delete(User).where(User.id == test_user.id))
    await db_session.commit()

    keys = (await db_session.execute(select(func.count()).select_from(APIKey))).scalar_one()
    events = (
        await db_session.execute(select(func.count()).select_from(RequestEventRecord))
    ).scalar_one()
    assert (keys, events) == (0, 0)
