import httpx
import pytest

from app.core.exceptions import ProviderRequestError
from app.providers.openrouter import OpenRouterProvider


def _client_with(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_forward_sends_bearer_auth_and_posts_to_chat_completions():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json={"id": "gen-1", "choices": []})

    provider = OpenRouterProvider(client=_client_with(handler))

    response = await provider.forward(
        key="sk-or-secret",
        path="v1/chat/completions",
        method="POST",
        payload={"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
        headers={},
    )

    assert response.status_code == 200
    sent = captured["request"]
    assert str(sent.url) == "https://openrouter.ai/api/v1/chat/completions"
    assert sent.headers["authorization"] == "Bearer sk-or-secret"


@pytest.mark.asyncio
async def test_forward_strips_inbound_authorization_header_and_keeps_others():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json={})

    provider = OpenRouterProvider(client=_client_with(handler))

    await provider.forward(
        key="sk-or-real-key",
        path="v1/chat/completions",
        method="POST",
        payload={},
        headers={"Authorization": "Bearer gwk_should_not_appear", "X-Custom": "keep-me"},
    )

    sent = captured["request"]
    # The gateway's own inbound Authorization header (the gwk_ token) must
    # never leak upstream — only the decrypted provider key should appear.
    assert sent.headers["authorization"] == "Bearer sk-or-real-key"
    assert sent.headers["x-custom"] == "keep-me"


def test_is_rate_limited_on_429():
    provider = OpenRouterProvider()
    assert provider.is_rate_limited(httpx.Response(429)) is True
    assert provider.is_rate_limited(httpx.Response(200)) is False


def test_is_key_exhausted_on_402_not_429():
    provider = OpenRouterProvider()
    # 402 Payment Required = out of credits (park the key); 429 is a
    # temporary throttle and must NOT be treated as exhausted.
    assert provider.is_key_exhausted(httpx.Response(402)) is True
    assert provider.is_key_exhausted(httpx.Response(429)) is False
    assert provider.is_key_exhausted(httpx.Response(200)) is False


@pytest.mark.asyncio
async def test_health_check_ok_on_200():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://openrouter.ai/api/v1/key"
        return httpx.Response(200, json={"data": {"limit": None, "usage": 0}})

    provider = OpenRouterProvider(client=_client_with(handler))

    result = await provider.health_check("sk-or-real-key")

    assert result.ok is True


@pytest.mark.asyncio
async def test_health_check_surfaces_upstream_error_message():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "No auth credentials found"}})

    provider = OpenRouterProvider(client=_client_with(handler))

    result = await provider.health_check("bad-key")

    assert result.ok is False
    assert "No auth credentials found" in result.detail


@pytest.mark.asyncio
async def test_health_check_handles_network_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    provider = OpenRouterProvider(client=_client_with(handler))

    result = await provider.health_check("sk-or-real-key")

    assert result.ok is False
    assert "Network error" in result.detail


@pytest.mark.asyncio
async def test_list_models_returns_ids_and_labels():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://openrouter.ai/api/v1/models"
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "openai/gpt-4o-mini", "name": "GPT-4o mini"},
                    {"id": "anthropic/claude-3.5-sonnet", "name": "Claude 3.5 Sonnet"},
                ]
            },
        )

    provider = OpenRouterProvider(client=_client_with(handler))

    models = await provider.list_models("sk-or-real-key")

    assert [m.model_id for m in models] == ["openai/gpt-4o-mini", "anthropic/claude-3.5-sonnet"]
    assert models[0].label == "GPT-4o mini"


@pytest.mark.asyncio
async def test_list_models_skips_entries_without_an_id():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"name": "no id here"}, {"id": "openai/gpt-4o-mini"}]})

    provider = OpenRouterProvider(client=_client_with(handler))

    models = await provider.list_models("sk-or-real-key")

    assert [m.model_id for m in models] == ["openai/gpt-4o-mini"]
    # Falls back to id when the upstream doesn't provide a friendlier name.
    assert models[0].label == "openai/gpt-4o-mini"


@pytest.mark.asyncio
async def test_list_models_raises_on_bad_key():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "No auth credentials found"}})

    provider = OpenRouterProvider(client=_client_with(handler))

    with pytest.raises(ProviderRequestError) as exc_info:
        await provider.list_models("bad-key")

    assert "No auth credentials found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_list_models_raises_on_network_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    provider = OpenRouterProvider(client=_client_with(handler))

    with pytest.raises(ProviderRequestError) as exc_info:
        await provider.list_models("sk-or-real-key")

    assert "Network error" in str(exc_info.value)
