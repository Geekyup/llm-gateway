import csv
import io
import logging

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.api.deps import get_activity_cache, get_event_publisher
from app.auth.deps import get_current_user
from app.auth.models import User
from app.monitoring.cache import ActivityCache
from app.monitoring.publisher import RequestEventPublisher
from app.monitoring.schemas import (
    ActivityLogResponse,
    ActivityRange,
    ActivitySummary,
    DailyTimeseriesResponse,
    LatencyPercentilesResponse,
    Outcome,
    TokensByProviderResponse,
    TopModelsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/me/activity", tags=["activity"])


@router.get("/summary", response_model=ActivitySummary)
async def summary(
    range: ActivityRange = Query(default="7d"),
    user: User = Depends(get_current_user),
    publisher: RequestEventPublisher = Depends(get_event_publisher),
    cache: ActivityCache = Depends(get_activity_cache),
) -> ActivitySummary:
    return await cache.get_or_load(
        user_id=user.id,
        endpoint="summary",
        params=range,
        model=ActivitySummary,
        loader=lambda: publisher.activity_summary(user.id, range),
    )


@router.get("/daily-timeseries", response_model=DailyTimeseriesResponse)
async def daily_timeseries(
    range: ActivityRange = Query(default="7d"),
    user: User = Depends(get_current_user),
    publisher: RequestEventPublisher = Depends(get_event_publisher),
    cache: ActivityCache = Depends(get_activity_cache),
) -> DailyTimeseriesResponse:
    async def load() -> DailyTimeseriesResponse:
        return DailyTimeseriesResponse(range=range, buckets=await publisher.daily_timeseries(user.id, range))

    return await cache.get_or_load(
        user_id=user.id,
        endpoint="daily-timeseries",
        params=range,
        model=DailyTimeseriesResponse,
        loader=load,
    )


@router.get("/latency-percentiles", response_model=LatencyPercentilesResponse)
async def latency_percentiles(
    range: ActivityRange = Query(default="7d"),
    user: User = Depends(get_current_user),
    publisher: RequestEventPublisher = Depends(get_event_publisher),
    cache: ActivityCache = Depends(get_activity_cache),
) -> LatencyPercentilesResponse:
    async def load() -> LatencyPercentilesResponse:
        return LatencyPercentilesResponse(
            range=range, buckets=await publisher.latency_percentiles_daily(user.id, range)
        )

    return await cache.get_or_load(
        user_id=user.id,
        endpoint="latency-percentiles",
        params=range,
        model=LatencyPercentilesResponse,
        loader=load,
    )


@router.get("/tokens-by-provider", response_model=TokensByProviderResponse)
async def tokens_by_provider(
    range: ActivityRange = Query(default="7d"),
    user: User = Depends(get_current_user),
    publisher: RequestEventPublisher = Depends(get_event_publisher),
    cache: ActivityCache = Depends(get_activity_cache),
) -> TokensByProviderResponse:
    async def load() -> TokensByProviderResponse:
        return TokensByProviderResponse(
            range=range, buckets=await publisher.tokens_by_provider_daily(user.id, range)
        )

    return await cache.get_or_load(
        user_id=user.id,
        endpoint="tokens-by-provider",
        params=range,
        model=TokensByProviderResponse,
        loader=load,
    )


@router.get("/top-models", response_model=TopModelsResponse)
async def top_models(
    range: ActivityRange = Query(default="7d"),
    limit: int = Query(default=10, ge=1, le=50),
    user: User = Depends(get_current_user),
    publisher: RequestEventPublisher = Depends(get_event_publisher),
    cache: ActivityCache = Depends(get_activity_cache),
) -> TopModelsResponse:
    async def load() -> TopModelsResponse:
        return TopModelsResponse(range=range, models=await publisher.top_models(user.id, range, limit=limit))

    return await cache.get_or_load(
        user_id=user.id,
        endpoint="top-models",
        params=f"{range}:{limit}",
        model=TopModelsResponse,
        loader=load,
    )


@router.get("/log", response_model=ActivityLogResponse)
async def activity_log(
    range: ActivityRange = Query(default="7d"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    provider: str | None = Query(default=None),
    outcome: Outcome | None = Query(default=None),
    user: User = Depends(get_current_user),
    publisher: RequestEventPublisher = Depends(get_event_publisher),
) -> ActivityLogResponse:
    entries, total = await publisher.activity_log(
        user.id, range, page=page, page_size=page_size, provider=provider, outcome=outcome
    )
    return ActivityLogResponse(entries=entries, page=page, page_size=page_size, total=total)


@router.get("/log/export.csv")
async def export_activity_log_csv(
    range: ActivityRange = Query(default="7d"),
    provider: str | None = Query(default=None),
    outcome: Outcome | None = Query(default=None),
    user: User = Depends(get_current_user),
    publisher: RequestEventPublisher = Depends(get_event_publisher),
) -> StreamingResponse:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["timestamp", "provider", "model", "key_label", "outcome", "latency_ms", "total_tokens", "upstream_status"])

    page = 1
    page_size = 500
    while True:
        entries, total = await publisher.activity_log(
            user.id, range, page=page, page_size=page_size, provider=provider, outcome=outcome
        )
        for entry in entries:
            writer.writerow(
                [
                    entry.timestamp.isoformat(),
                    entry.provider,
                    entry.model or "",
                    entry.key_label or "",
                    entry.outcome,
                    entry.latency_ms if entry.latency_ms is not None else "",
                    entry.total_tokens if entry.total_tokens is not None else "",
                    entry.upstream_status if entry.upstream_status is not None else "",
                ]
            )
        if page * page_size >= total or not entries:
            break
        page += 1

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=activity-{range}.csv"},
    )
