from datetime import datetime

from pydantic import BaseModel, Field


class RequestEvent(BaseModel):
    """One hop of a proxied request: a single (key, upstream call) pair.

    A single incoming client request can produce several of these if the
    gateway retries with a different key after a 429/exhausted response —
    they share `request_id` so the frontend can render them as one chain.
    """

    user_id: int = Field(..., description="Owner of the gateway token that made this request")
    request_id: str = Field(..., description="Shared across all attempts of the same client request")
    attempt: int = Field(..., description="1-indexed attempt number within this request")
    timestamp: datetime

    provider: str
    path: str
    method: str

    key_id: int | None = Field(default=None, description="None if no key was available at all")
    key_label: str | None = None

    upstream_status: int | None = Field(default=None, description="HTTP status from upstream, if the call was made")
    outcome: str = Field(
        ...,
        description="One of: success, rate_limited, exhausted, no_keys, upstream_exhausted, error",
    )
    latency_ms: int | None = Field(default=None, description="Time spent on this specific upstream call")
    is_retry: bool = Field(default=False, description="True for attempt > 1")
    error_detail: str | None = None


class RequestEventList(BaseModel):
    events: list[RequestEvent]


class HourlyUsagePoint(BaseModel):
    hour: int = Field(..., ge=0, le=23, description="UTC hour of day, 0-23")
    requests: int = Field(..., ge=0)


class HourlyUsageResponse(BaseModel):
    key_id: int
    points: list[HourlyUsagePoint]
