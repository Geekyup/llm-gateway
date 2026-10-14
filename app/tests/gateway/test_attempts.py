import httpx
import pytest

from app.gateway.attempts import NO_USAGE, Outcome, TokenUsage, Verdict, classify_response
from app.gateway.proxy_service import _scope
from app.gateway.usage import extract_usage
from app.keys.enums import ProviderType
from app.providers.base import Provider


class _StatusProvider(Provider):
    def is_rate_limited(self, response: httpx.Response) -> bool:
        return response.status_code == 429

    def is_key_exhausted(self, response: httpx.Response) -> bool:
        return response.status_code == 403

    def is_key_invalid(self, response: httpx.Response) -> bool:
        return response.status_code == 401


@pytest.mark.parametrize(
    ("status_code", "verdict"),
    [
        (200, Verdict.SUCCESS),
        (204, Verdict.SUCCESS),
        (401, Verdict.KEY_INVALID),
        (403, Verdict.KEY_EXHAUSTED),
        (429, Verdict.RATE_LIMITED),
        (500, Verdict.SERVER_ERROR),
        (503, Verdict.SERVER_ERROR),
        (400, Verdict.CLIENT_ERROR),
        (404, Verdict.CLIENT_ERROR),
    ],
)
def test_classify_response(status_code, verdict):
    assert classify_response(_StatusProvider(), httpx.Response(status_code)) is verdict


def test_provider_key_checks_take_precedence_over_generic_status_ranges():
    class QuotaAs5xx(_StatusProvider):
        def is_key_exhausted(self, response: httpx.Response) -> bool:
            return response.status_code == 503

    assert classify_response(QuotaAs5xx(), httpx.Response(503)) is Verdict.KEY_EXHAUSTED


@pytest.mark.parametrize(
    ("verdict", "outcome", "retryable"),
    [
        (Verdict.SUCCESS, Outcome.SUCCESS, False),
        (Verdict.KEY_INVALID, Outcome.INVALID, True),
        (Verdict.KEY_EXHAUSTED, Outcome.EXHAUSTED, True),
        (Verdict.RATE_LIMITED, Outcome.RATE_LIMITED, True),
        (Verdict.SERVER_ERROR, Outcome.ERROR, True),
        (Verdict.CLIENT_ERROR, Outcome.ERROR, False),
    ],
)
def test_verdict_maps_to_reported_outcome_and_retry_policy(verdict, outcome, retryable):
    assert verdict.outcome is outcome
    assert verdict.retryable is retryable


def test_outcome_values_are_the_persisted_labels():
    assert {o.value for o in Outcome} == {
        "success", "invalid", "exhausted", "rate_limited", "error", "no_keys", "upstream_exhausted",
    }


def test_extract_usage_reads_gemini_usage_metadata():
    response = httpx.Response(
        200,
        json={"usageMetadata": {"promptTokenCount": 3, "candidatesTokenCount": 5, "totalTokenCount": 8}},
    )
    assert extract_usage(response) == TokenUsage(prompt=3, completion=5, total=8)


def test_extract_usage_reads_openai_usage():
    response = httpx.Response(
        200, json={"usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}}
    )
    assert extract_usage(response) == TokenUsage(prompt=1, completion=2, total=3)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, json={"ok": True}),
        httpx.Response(200, json={"usage": None}),
        httpx.Response(200, json={"usageMetadata": None}),
        httpx.Response(200, content=b"not json"),
        httpx.Response(200, json=[1, 2, 3]),
    ],
)
def test_extract_usage_never_raises_and_falls_back_to_no_usage(response):
    assert extract_usage(response) == NO_USAGE


def test_scope_names_the_model_only_when_one_was_requested():
    assert _scope(ProviderType.GEMINI, None) == "gemini"
    assert _scope(None, None) == "any"
    assert _scope(ProviderType.GEMINI, "flash") == "gemini' for model 'flash"
