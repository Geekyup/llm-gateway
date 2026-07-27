import httpx
import pytest

from app.core.exceptions import ProviderRequestError
from app.providers.gemini import GeminiProvider


def _client_with(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_list_models_strips_models_prefix_and_filters_to_generate_content():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://generativelanguage.googleapis.com/v1beta/models"
        return httpx.Response(
            200,
            json={
                "models": [
                    {
                        "name": "models/gemini-3.6-flash",
                        "displayName": "Gemini 3.6 Flash",
                        "supportedGenerationMethods": ["generateContent"],
                    },
                    {
                        "name": "models/embedding-001",
                        "displayName": "Embedding 001",
                        # Doesn't support generateContent — this gateway only
                        # ever calls generateContent, so listing it would
                        # just let someone pin a key to a model that 404s.
                        "supportedGenerationMethods": ["embedContent"],
                    },
                ]
            },
        )

    provider = GeminiProvider(client=_client_with(handler))

    models = await provider.list_models("AIza-real-key")

    assert [m.id for m in models] == ["gemini-3.6-flash"]
    assert models[0].label == "Gemini 3.6 Flash"


@pytest.mark.asyncio
async def test_list_models_falls_back_to_id_when_no_display_name():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"models": [{"name": "models/gemini-3.6-flash", "supportedGenerationMethods": ["generateContent"]}]},
        )

    provider = GeminiProvider(client=_client_with(handler))

    models = await provider.list_models("AIza-real-key")

    assert models[0].label == "gemini-3.6-flash"


@pytest.mark.asyncio
async def test_list_models_raises_on_bad_key():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "API key not valid. Please pass a valid API key."}})

    provider = GeminiProvider(client=_client_with(handler))

    with pytest.raises(ProviderRequestError) as exc_info:
        await provider.list_models("bad-key")

    assert "API key not valid" in str(exc_info.value)


@pytest.mark.asyncio
async def test_list_models_raises_on_network_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    provider = GeminiProvider(client=_client_with(handler))

    with pytest.raises(ProviderRequestError) as exc_info:
        await provider.list_models("AIza-real-key")

    assert "Network error" in str(exc_info.value)
