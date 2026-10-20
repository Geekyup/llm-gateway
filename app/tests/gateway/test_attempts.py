import httpx
import pytest

from app.core.exceptions import NoAvailableKeysError
from app.gateway.attempts import NO_USAGE, Attempt, TokenUsage, Verdict, classify_response
from app.gateway.proxy_service import GatewayService
from app.gateway.reporting import extract_usage
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
    ("verdict", "label", "retryable"),
    [
        (Verdict.SUCCESS, "success", False),
        (Verdict.KEY_INVALID, "invalid", True),
        (Verdict.KEY_EXHAUSTED, "exhausted", True),
        (Verdict.RATE_LIMITED, "rate_limited", True),
        (Verdict.SERVER_ERROR, "error", True),
        (Verdict.NETWORK_ERROR, "error", True),
        (Verdict.CLIENT_ERROR, "error", False),
    ],
)
def test_verdict_carries_persisted_label_and_retry_policy(verdict, label, retryable):
    assert verdict.label == label
    assert verdict.retryable is retryable


def test_every_verdict_is_a_distinct_member():
    assert len(list(Verdict)) == 7


def _attempt() -> Attempt:
    return Attempt(
        user_id=1,
        request_id="r1",
        number=2,
        key=None,
        provider=_StatusProvider(),
        spec=None,
        model=None,
    )


def test_finish_records_latency_status_and_http_error_detail():
    attempt = _attempt()

    attempt.finish(Verdict.SERVER_ERROR, response=httpx.Response(503))

    assert attempt.verdict is Verdict.SERVER_ERROR
    assert attempt.status_code == 503
    assert attempt.error_detail == "HTTP 503"
    assert attempt.latency_ms is not None and attempt.latency_ms >= 0
    assert attempt.is_retry is True


def test_finish_records_exception_name_for_network_errors():
    attempt = _attempt()

    attempt.finish(Verdict.NETWORK_ERROR, error=httpx.ConnectError("boom"))

    assert attempt.status_code is None
    assert attempt.error_detail == "ConnectError"


def test_finish_leaves_error_detail_empty_on_success_and_key_problems():
    for verdict, status in ((Verdict.SUCCESS, 200), (Verdict.RATE_LIMITED, 429)):
        attempt = _attempt()
        attempt.finish(verdict, response=httpx.Response(status))
        assert attempt.error_detail is None


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


class _EmptyPool:
    async def select_key(self, *args, **kwargs):
        return None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_type", "model", "expected"),
    [
        (ProviderType.GEMINI, "flash", "gemini' for model 'flash'"),
        (ProviderType.GEMINI, None, "gemini'"),
        (None, None, "any'"),
    ],
)
async def test_no_keys_error_names_provider_and_requested_model(provider_type, model, expected):
    service = GatewayService(_EmptyPool(), max_attempts=3)

    with pytest.raises(NoAvailableKeysError) as exc_info:
        await service.proxy_request(
            user_id=1,
            build_request=lambda key: None,
            provider_type=provider_type,
            model=model,
        )

    assert expected in str(exc_info.value)
