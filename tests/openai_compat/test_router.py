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
async def test_default_provider_is_gemini_and_translates_payload():
    gateway = RecordingGateway(httpx.Response(200, json={"candidates": []}))
    request = ChatCompletionRequest(model="gemini-3.6-flash", messages=[ChatMessage(role="user", content="hi")])

    await chat_completions(request, gateway=gateway, user_id=1)

    assert len(gateway.calls) == 1
    call = gateway.calls[0]
    assert call["provider_type"] is ProviderType.GEMINI
    assert call["path"] == "v1beta/models/gemini-3.6-flash:generateContent"
    assert "contents" in call["payload"]
    assert "messages" not in call["payload"]


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
    assert call["path"] == "v1/chat/completions"
    assert call["payload"]["model"] == "openai/gpt-4o-mini"
    assert call["payload"]["messages"] == [{"role": "user", "content": "hi"}]
    assert "provider" not in call["payload"]


@pytest.mark.asyncio
async def test_openrouter_response_passed_through_unmodified():
    upstream_body = {"id": "gen-1", "choices": [{"message": {"role": "assistant", "content": "hey"}}], "usage": {"total_tokens": 5}}
    gateway = RecordingGateway(httpx.Response(200, json=upstream_body))
    request = ChatCompletionRequest(model="openai/gpt-4o-mini", messages=[ChatMessage(role="user", content="hi")], provider="openrouter")

    response = await chat_completions(request, gateway=gateway, user_id=1)

    import json
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
