from functools import lru_cache

from app.core.exceptions import ProviderNotSupportedError
from app.providers.base import Provider
from app.providers.gemini import GeminiProvider


@lru_cache
def _registry() -> dict[str, Provider]:
    return {
        GeminiProvider.name: GeminiProvider(),
        # Add new providers here as they're implemented, e.g.:
        # OpenAIProvider.name: OpenAIProvider(),
    }


def get_provider(name: str) -> Provider:
    try:
        return _registry()[name]
    except KeyError as exc:
        raise ProviderNotSupportedError(provider=name) from exc
