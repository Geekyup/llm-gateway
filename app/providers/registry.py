from functools import lru_cache

import httpx

from app.config import get_settings
from app.core.exceptions import ProviderNotSupportedError
from app.providers.base import Provider
from app.providers.gemini import GeminiProvider
from app.providers.groq import GroqProvider
from app.providers.openrouter import OpenRouterProvider


@lru_cache
def _shared_client() -> httpx.AsyncClient:
    settings = get_settings()
    return httpx.AsyncClient(timeout=settings.UPSTREAM_TIMEOUT_SECONDS)


@lru_cache
def _registry() -> dict[str, Provider]:
    client = _shared_client()
    return {
        GeminiProvider.name: GeminiProvider(client=client),
        OpenRouterProvider.name: OpenRouterProvider(client=client),
        GroqProvider.name: GroqProvider(client=client),
    }


def get_provider(name: str) -> Provider:
    try:
        return _registry()[name]
    except KeyError as exc:
        raise ProviderNotSupportedError(provider=name) from exc