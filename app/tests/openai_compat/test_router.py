import json

import httpx
import pytest

from app.core.exceptions import NoAvailableKeysError
from app.keys.enums import KeyStatus, ProviderType
from app.keys.schemas import APIKeyDTO
from app.openai_compat.router import chat_completions
from app.openai_compat.schemas import ChatCompletionRequest, ChatMessage


def _fake_dto(provider: ProviderType, model: str | None = None) -> APIKeyDTO:
    return APIKeyDTO(
        id=1, user_id=1, label="k", provider=provider, status=KeyStatus.ACTIVE,
        requests_today=0, daily_limit=100, model=model, decrypted_key="raw",
    )


class RecordingGateway:
    def __init__(self, response: httpx.Response | None = None, raise_: Exception | None = None) -> None:
        self.response = response
        self.raise_ = raise_
        self.calls: list[dict] = []

    async def proxy_request(self, **kwargs):
        self.calls.append(kwargs)
        if self.raise_:
            raise self.raise_
        return self.response


class RecordingStreamGateway:

    def __init__(
        self,
        status_code: int = 200,
        body_lines: list[str] | None = None,
        upstream_url: str = "http://upstream/v1/chat/completions",
        raise_: Exception | None = None,
    ) -> None:
        self.status_code = status_code
        self.body_lines = body_lines or []
        self.upstream_url = upstream_url
        self.raise_ = raise_
        self.calls: list[dict] = []
        self.recorded_tokens: list[tuple] = []

    def proxy_stream_request(self, **kwargs):
        self.calls.append(kwargs)
        if self.raise_:
            raise self.raise_
        return _FakeStreamCtx(self)


class _FakeStreamCtx:
    def __init__(self, gateway: RecordingStreamGateway) -> None:
        self._gateway = gateway

    async def __aenter__(self):
        body = "\n\n".join(self._gateway.body_lines).encode()
        response = httpx.Response(
            status_code=self._gateway.status_code,
            content=body,
            request=httpx.Request("POST", self._gateway.upstream_url),
        )

        async def record_tokens(prompt_tokens, completion_tokens, total_tokens):
            self._gateway.recorded_tokens.append((prompt_tokens, completion_tokens, total_tokens))

        return response, record_tokens

    async def __aexit__(self, *exc_info) -> None:
        return None


@pytest.mark.asyncio
async def test_no_explicit_provider_searches_across_all_providers():
    gateway = RecordingGateway(httpx.Response(200, json={"candidates": []}))
    request = ChatCompletionRequest(model="gemini-3.6-flash", messages=[ChatMessage(role="user", content="hi")])

    await chat_completions(request, gateway=gateway, user_id=1)

    assert len(gateway.calls) == 1
    call = gateway.calls[0]

    assert call["provider_type"] is None
    assert call["model"] == "gemini-3.6-flash"

    spec = call["build_request"](_fake_dto(ProviderType.GEMINI))
    assert spec.path == "v1beta/models/gemini-3.6-flash:generateContent"
    assert "contents" in spec.payload
    assert "messages" not in spec.payload


@pytest.mark.asyncio
async def test_explicit_gemini_provider_scopes_pool_search():
    gateway = RecordingGateway(httpx.Response(200, json={"candidates": []}))
    request = ChatCompletionRequest(
        model="gemini-3.6-flash", messages=[ChatMessage(role="user", content="hi")], provider="gemini"
    )

    await chat_completions(request, gateway=gateway, user_id=1)

    assert len(gateway.calls) == 1
    call = gateway.calls[0]
    assert call["provider_type"] is ProviderType.GEMINI


@pytest.mark.asyncio
async def test_explicit_openrouter_provider_passes_payload_through():
    gateway = RecordingGateway(httpx.Response(200, json={"id": "gen-1", "choices": [], "usage": {}}))
    request = ChatCompletionRequest(
        model="openai/gpt-4o-mini",
        messages=[ChatMessage(role="user", content="hi")],
        provider="openrouter",
    )

    await chat_completions(request, gateway=gateway, user_id=1)

    assert len(gateway.calls) == 1
    call = gateway.calls[0]
    assert call["provider_type"] is ProviderType.OPENROUTER

    spec = call["build_request"](_fake_dto(ProviderType.OPENROUTER))
    assert spec.path == "v1/chat/completions"
    assert spec.payload["model"] == "openai/gpt-4o-mini"
    assert spec.payload["messages"] == [{"role": "user", "content": "hi"}]
    assert "provider" not in spec.payload


@pytest.mark.asyncio
async def test_key_pinned_model_wins_over_request_model():
    gateway = RecordingGateway(httpx.Response(200, json={"candidates": []}))
    request = ChatCompletionRequest(
        model="gemini-3.6-flash", messages=[ChatMessage(role="user", content="hi")]
    )

    await chat_completions(request, gateway=gateway, user_id=1)

    call = gateway.calls[0]
    pinned_dto = _fake_dto(ProviderType.GEMINI, model="gemini-1.5-pro")
    spec = call["build_request"](pinned_dto)
    assert spec.path == "v1beta/models/gemini-1.5-pro:generateContent"


@pytest.mark.asyncio
async def test_no_model_no_provider_falls_back_to_default_model_for_openrouter_key():
    gateway = RecordingGateway(httpx.Response(200, json={"id": "gen-1", "choices": [], "usage": {}}))
    request = ChatCompletionRequest(messages=[ChatMessage(role="user", content="hi")])

    await chat_completions(request, gateway=gateway, user_id=1)

    call = gateway.calls[0]
    assert call["provider_type"] is None
    assert call["model"] is None

    spec = call["build_request"](_fake_dto(ProviderType.OPENROUTER, model=None))
    assert spec.payload["model"]  # some default model string, non-empty


@pytest.mark.asyncio
async def test_openrouter_response_passed_through_unmodified():
    upstream_body = {"id": "gen-1", "choices": [{"message": {"role": "assistant", "content": "hey"}}], "usage": {"total_tokens": 5}}
    gateway = RecordingGateway(httpx.Response(200, json=upstream_body))
    request = ChatCompletionRequest(model="openai/gpt-4o-mini", messages=[ChatMessage(role="user", content="hi")], provider="openrouter")

    response = await chat_completions(request, gateway=gateway, user_id=1)

    assert json.loads(response.body) == upstream_body


@pytest.mark.asyncio
async def test_unknown_provider_returns_400_without_calling_gateway():
    gateway = RecordingGateway()
    request = ChatCompletionRequest(model="whatever", messages=[ChatMessage(role="user", content="hi")], provider="not-a-real-provider")

    response = await chat_completions(request, gateway=gateway, user_id=1)

    assert response.status_code == 400
    assert gateway.calls == []


@pytest.mark.asyncio
async def test_no_available_keys_surfaces_as_503():
    gateway = RecordingGateway(raise_=NoAvailableKeysError(provider="openrouter"))
    request = ChatCompletionRequest(model="openai/gpt-4o-mini", messages=[ChatMessage(role="user", content="hi")], provider="openrouter")

    response = await chat_completions(request, gateway=gateway, user_id=1)

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_stream_openrouter_records_tokens_from_final_usage_chunk():

    body_lines = [
        'data: {"choices": [{"delta": {"content": "Hi"}}]}',
        'data: {"choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13}}',
        "data: [DONE]",
    ]
    gateway = RecordingStreamGateway(
        status_code=200,
        body_lines=body_lines,
        upstream_url="http://upstream/v1/chat/completions",
    )
    request = ChatCompletionRequest(
        model="openai/gpt-4o-mini",
        messages=[ChatMessage(role="user", content="hi")],
        provider="openrouter",
        stream=True,
    )

    response = await chat_completions(request, gateway=gateway, user_id=1)

    chunks = [chunk async for chunk in response.body_iterator]
    assert b"".join(
        c if isinstance(c, bytes) else c.encode() for c in chunks
    )  

    assert gateway.recorded_tokens == [(10, 3, 13)]


@pytest.mark.asyncio
async def test_stream_openrouter_requests_usage_via_stream_options():
    gateway = RecordingStreamGateway(
        status_code=200,
        body_lines=['data: {"choices": [], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}', "data: [DONE]"],
    )
    request = ChatCompletionRequest(
        model="openai/gpt-4o-mini",
        messages=[ChatMessage(role="user", content="hi")],
        provider="openrouter",
        stream=True,
    )

    response = await chat_completions(request, gateway=gateway, user_id=1)
    _ = [chunk async for chunk in response.body_iterator]

    call = gateway.calls[0]
    spec = call["build_request"](_fake_dto(ProviderType.OPENROUTER))
    assert spec.payload["stream"] is True
    assert spec.payload["stream_options"] == {"include_usage": True}


@pytest.mark.asyncio
async def test_stream_gemini_records_tokens_from_usage_metadata():
    body_lines = [
        'data: {"candidates": [{"content": {"parts": [{"text": "Hi"}]}}], "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 1, "totalTokenCount": 6}}',
        'data: {"candidates": [{"content": {"parts": [{"text": "!"}]}, "finishReason": "STOP"}], "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 2, "totalTokenCount": 7}}',
    ]
    gateway = RecordingStreamGateway(
        status_code=200,
        body_lines=body_lines,
        upstream_url="http://upstream/v1beta/models/gemini-1.5-flash:streamGenerateContent?alt=sse",
    )
    request = ChatCompletionRequest(
        model="gemini-1.5-flash",
        messages=[ChatMessage(role="user", content="hi")],
        provider="gemini",
        stream=True,
    )

    response = await chat_completions(request, gateway=gateway, user_id=1)
    _ = [chunk async for chunk in response.body_iterator]

    assert gateway.recorded_tokens == [(5, 2, 7)]


@pytest.mark.asyncio
async def test_stream_upstream_error_does_not_record_tokens():
    gateway = RecordingStreamGateway(status_code=429, body_lines=['{"error": {"message": "rate limited"}}'])
    request = ChatCompletionRequest(
        model="openai/gpt-4o-mini",
        messages=[ChatMessage(role="user", content="hi")],
        provider="openrouter",
        stream=True,
    )

    response = await chat_completions(request, gateway=gateway, user_id=1)

    assert response.status_code == 429
    assert gateway.recorded_tokens == []