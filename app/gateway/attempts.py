import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import NamedTuple

import httpx

from app.keys.enums import ProviderType
from app.keys.schemas import APIKeyDTO
from app.providers.base import Provider


@dataclass(frozen=True, slots=True)
class UpstreamRequestSpec:
    path: str
    method: str
    payload: dict | None
    headers: dict


RequestSpecBuilder = Callable[[APIKeyDTO], UpstreamRequestSpec]

TokenRecorder = Callable[[int | None, int | None, int | None], Awaitable[None]]


class TokenUsage(NamedTuple):
    prompt: int | None = None
    completion: int | None = None
    total: int | None = None


NO_USAGE = TokenUsage()


class Verdict(Enum):
    SUCCESS = ("success", False, "success")
    KEY_INVALID = ("invalid", True, "key invalid")
    KEY_EXHAUSTED = ("exhausted", True, "key exhausted")
    RATE_LIMITED = ("rate_limited", True, "rate limited")
    SERVER_ERROR = ("error", True, "upstream server error")
    CLIENT_ERROR = ("error", False, "client error")
    NETWORK_ERROR = ("error", True, "network error")

    def __init__(self, label: str, retryable: bool, description: str) -> None:
        self.label = label
        self.retryable = retryable
        self.description = description


def classify_response(provider: Provider, response: httpx.Response) -> Verdict:
    if provider.is_key_invalid(response):
        return Verdict.KEY_INVALID
    if provider.is_key_exhausted(response):
        return Verdict.KEY_EXHAUSTED
    if provider.is_rate_limited(response):
        return Verdict.RATE_LIMITED
    if response.status_code >= 500:
        return Verdict.SERVER_ERROR
    if response.status_code >= 400:
        return Verdict.CLIENT_ERROR
    return Verdict.SUCCESS


@dataclass(slots=True)
class Attempt:
    user_id: int
    request_id: str
    number: int
    key: APIKeyDTO
    provider: Provider
    spec: UpstreamRequestSpec
    model: str | None
    started_at: float = field(default_factory=time.monotonic)
    verdict: Verdict | None = None
    response: httpx.Response | None = None
    latency_ms: int | None = None
    error_detail: str | None = None

    @property
    def provider_type(self) -> ProviderType:
        return self.key.provider

    @property
    def is_retry(self) -> bool:
        return self.number > 1

    @property
    def status_code(self) -> int | None:
        return self.response.status_code if self.response is not None else None

    def finish(
        self,
        verdict: Verdict,
        *,
        response: httpx.Response | None = None,
        error: Exception | None = None,
    ) -> None:
        self.latency_ms = int((time.monotonic() - self.started_at) * 1000)
        self.verdict = verdict
        self.response = response
        if error is not None:
            self.error_detail = type(error).__name__
        elif verdict in (Verdict.SERVER_ERROR, Verdict.CLIENT_ERROR):
            self.error_detail = f"HTTP {response.status_code}"


def provider_label(provider_type: ProviderType | None) -> str:
    return provider_type.value if provider_type is not None else "any"
