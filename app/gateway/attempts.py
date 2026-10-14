from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum, StrEnum

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


@dataclass(frozen=True, slots=True)
class TokenUsage:
    prompt: int | None = None
    completion: int | None = None
    total: int | None = None


NO_USAGE = TokenUsage()


class Outcome(StrEnum):
    SUCCESS = "success"
    INVALID = "invalid"
    EXHAUSTED = "exhausted"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"
    NO_KEYS = "no_keys"
    UPSTREAM_EXHAUSTED = "upstream_exhausted"


class Verdict(Enum):
    SUCCESS = (Outcome.SUCCESS, False)
    KEY_INVALID = (Outcome.INVALID, True)
    KEY_EXHAUSTED = (Outcome.EXHAUSTED, True)
    RATE_LIMITED = (Outcome.RATE_LIMITED, True)
    SERVER_ERROR = (Outcome.ERROR, True)
    CLIENT_ERROR = (Outcome.ERROR, False)

    def __init__(self, outcome: Outcome, retryable: bool) -> None:
        self.outcome = outcome
        self.retryable = retryable


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


@dataclass(frozen=True, slots=True)
class AttemptContext:
    user_id: int
    request_id: str
    attempt: int
    key: APIKeyDTO
    provider: Provider
    spec: UpstreamRequestSpec
    effective_model: str | None

    @property
    def provider_type(self) -> ProviderType:
        return self.key.provider

    @property
    def is_retry(self) -> bool:
        return self.attempt > 1


def provider_label(provider_type: ProviderType | None) -> str:
    return provider_type.value if provider_type is not None else "any"
