from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Outcome = Literal["success", "rate_limited", "exhausted", "no_keys", "upstream_exhausted", "error"]


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