from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Outcome = Literal["success", "rate_limited", "exhausted", "no_keys", "upstream_exhausted", "error"]
MonitorRange = Literal["30m", "6h", "24h"]
ActivityRange = Literal["24h", "7d", "30d"]


class RequestEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: int = Field(..., description="Owner of the gateway token that made this request")
    request_id: str = Field(..., description="Shared across all attempts of the same client request")
    attempt: int = Field(..., description="1-indexed attempt number within this request")
    timestamp: datetime

    provider: str
    path: str
    method: str

    key_id: int | None = Field(default=None, description="None if no key was available at all")
    key_label: str | None = None
    model: str | None = Field(default=None, description="Requested model, if known at emit time")

    upstream_status: int | None = None
    outcome: Outcome
    latency_ms: int | None = Field(default=None, description="Time spent on this specific upstream call")
    is_retry: bool = Field(default=False, description="True for attempt > 1")
    error_detail: str | None = None

    prompt_tokens: int | None = Field(default=None, description="From upstream usage data, success only")
    completion_tokens: int | None = None
    total_tokens: int | None = None


class RequestEventList(BaseModel):
    events: list[RequestEvent]


class HourlyPoint(BaseModel):
    hour: int = Field(..., ge=0, le=23, description="UTC hour of day, 0-23")


class HourlyUsagePoint(HourlyPoint):
    requests: int = Field(..., ge=0)


class HourlyUsageResponse(BaseModel):
    key_id: int
    points: list[HourlyUsagePoint]


class HourlyTokenPoint(HourlyPoint):
    prompt_tokens: int = Field(..., ge=0)
    completion_tokens: int = Field(..., ge=0)
    total_tokens: int = Field(..., ge=0)


class HourlyTokenUsageResponse(BaseModel):
    key_id: int
    points: list[HourlyTokenPoint]


class TimeseriesBucket(BaseModel):
    ts: int = Field(..., description="Bucket start, unix ms")
    count: int = Field(..., ge=0)
    p50: float | None = Field(default=None, description="Median latency in ms, null if no data")
    providers: dict[str, int] = Field(default_factory=dict, description="Request count per provider in this bucket")


class TimeseriesResponse(BaseModel):
    range: MonitorRange
    buckets: list[TimeseriesBucket]


class ActivitySummary(BaseModel):
    total_requests: int = Field(..., ge=0)
    prev_total_requests: int = Field(..., ge=0)
    success_rate: float = Field(..., ge=0, le=100, description="Percent of success outcomes")
    prev_success_rate: float = Field(..., ge=0, le=100)
    latency_p50: float | None = None
    latency_p95: float | None = None
    prev_latency_p95: float | None = None
    total_tokens: int = Field(..., ge=0)
    prev_total_tokens: int = Field(..., ge=0)


class DailyOutcomeBucket(BaseModel):
    date: str = Field(..., description="ISO date, YYYY-MM-DD")
    success: int = Field(..., ge=0)
    rate_limited: int = Field(..., ge=0)
    error: int = Field(..., ge=0)


class DailyTimeseriesResponse(BaseModel):
    range: ActivityRange
    buckets: list[DailyOutcomeBucket]


class LatencyPercentileBucket(BaseModel):
    date: str
    p50: float | None = None
    p95: float | None = None
    p99: float | None = None


class LatencyPercentilesResponse(BaseModel):
    range: ActivityRange
    buckets: list[LatencyPercentileBucket]


class TokensByProviderBucket(BaseModel):
    date: str
    providers: dict[str, int] = Field(default_factory=dict)


class TokensByProviderResponse(BaseModel):
    range: ActivityRange
    buckets: list[TokensByProviderBucket]


class TopModelEntry(BaseModel):
    model: str
    provider: str
    requests: int = Field(..., ge=0)
    total_tokens: int = Field(..., ge=0)


class TopModelsResponse(BaseModel):
    range: ActivityRange
    models: list[TopModelEntry]


class ActivityLogEntry(BaseModel):
    id: int
    timestamp: datetime
    provider: str
    model: str | None = None
    key_label: str | None = None
    outcome: Outcome
    latency_ms: int | None = None
    total_tokens: int | None = None
    upstream_status: int | None = None


class ActivityLogResponse(BaseModel):
    entries: list[ActivityLogEntry]
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
    total: int = Field(..., ge=0)