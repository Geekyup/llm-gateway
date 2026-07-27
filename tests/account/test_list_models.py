"""Tests for the /me/keys/list-models endpoint's own logic (provider
lookup + response shaping). Provider.list_models itself is already
covered per-provider in tests/providers/ — these just confirm the
endpoint wires things together correctly, in the same "call the FastAPI
function directly" style as tests/openai_compat/test_router.py (no
TestClient/AsyncClient pattern exists elsewhere in this suite).
"""
import pytest

from app.account.keys_router import ListModelsRequest, list_models
from app.core.exceptions import ProviderNotSupportedError, ProviderRequestError
from app.keys.enums import ProviderType
from app.providers.base import ModelInfo


class FakeUser:
    id = 1


@pytest.mark.asyncio
async def test_returns_models_from_the_selected_provider(monkeypatch):
    async def fake_list_models(self, key):
        assert key == "sk-or-test"
        return [ModelInfo(id="openai/gpt-4o-mini", label="GPT-4o mini")]

    monkeypatch.setattr("app.providers.openrouter.OpenRouterProvider.list_models", fake_list_models)

    response = await list_models(
        ListModelsRequest(provider=ProviderType.OPENROUTER, raw_key="sk-or-test"),
        user=FakeUser(),
    )

    assert len(response.models) == 1
    assert response.models[0].id == "openai/gpt-4o-mini"
    assert response.models[0].label == "GPT-4o mini"


@pytest.mark.asyncio
async def test_propagates_provider_request_error_for_a_bad_key(monkeypatch):
    async def fake_list_models(self, key):
        raise ProviderRequestError(provider="gemini", reason="HTTP 400: API key not valid")

    monkeypatch.setattr("app.providers.gemini.GeminiProvider.list_models", fake_list_models)

    with pytest.raises(ProviderRequestError):
        await list_models(
            ListModelsRequest(provider=ProviderType.GEMINI, raw_key="bad-key"),
            user=FakeUser(),
        )


@pytest.mark.asyncio
async def test_unknown_provider_raises_provider_not_supported():
    # Pydantic validates `provider` against the ProviderType enum before
    # this function body ever runs, so an invalid string never reaches
    # here — this instead confirms get_provider's own guard would fire if
    # the registry and the enum were ever to drift apart.
    with pytest.raises(ProviderNotSupportedError):
        from app.providers.registry import get_provider

        get_provider("not-a-real-provider")
