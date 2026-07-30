import json

import httpx
import pytest

from app.core.exceptions import NoAvailableKeysError
from app.keys.enums import ProviderType
from app.openai_compat.router import chat_completions
from app.openai_compat.schemas import ChatCompletionRequest, ChatMessage


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


@pytest.mark.asyncio
async def test_no_explicit_provider_searches_across_all_providers():
    gateway = RecordingGateway(httpx.Response(200, json={"candidates": []}))
    request = ChatCompletionRequest(model="gemini-3.6-flash", messages=[ChatMessage(role="user", content="hi")])

    await chat_completions(request, gateway=gateway, user_id=1)

    assert len(gateway.calls) == 1
    call = gateway.calls[0]
    # No provider given -> pool search spans every provider (provider_type=None),
    # not just Gemini.
    assert call["provider_type"] is None
    assert call["model"] == "gemini-3.6-flash"

    # The request actually sent for a Gemini-provider key must still be
    # translated to Gemini's wire format.
    spec = call["build_request"](ProviderType.GEMINI)
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

    spec = call["build_request"](ProviderType.OPENROUTER)
    assert spec.path == "v1/chat/completions"
    assert spec.payload["model"] == "openai/gpt-4o-mini"
    assert spec.payload["messages"] == [{"role": "user", "content": "hi"}]
    assert "provider" not in spec.payload


@pytest.mark.asyncio
async def test_no_model_no_provider_omits_model_for_openrouter_style_key():
    """A request with neither model nor provider set that ends up on an
    OpenRouter-provider key must not send a null/absent 'model' the upstream
    would choke on — it's simply omitted, letting the upstream pick."""
    gateway = RecordingGateway(httpx.Response(200, json={"id": "gen-1", "choices": [], "usage": {}}))
    request = ChatCompletionRequest(messages=[ChatMessage(role="user", content="hi")])

    await chat_completions(request, gateway=gateway, user_id=1)

    call = gateway.calls[0]
    assert call["provider_type"] is None
    assert call["model"] is None

    spec = call["build_request"](ProviderType.OPENROUTER)
    assert "model" not in spec.payload


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