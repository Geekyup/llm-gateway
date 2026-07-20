from functools import lru_cache

from llm_gateway.core.exceptions import ProviderNotSupportedError
from llm_gateway.providers.base import Provider
from llm_gateway.providers.gemini import GeminiProvider


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
        raise ProviderNotSupportedError(name) from exc
