from typing import ClassVar

import httpx

from app.config import get_settings
from app.providers.base import HTTPProvider


class OpenRouterProvider(HTTPProvider):
    name: ClassVar[str] = "openrouter"
    _MODELS_PATH: ClassVar[str] = "v1/models"
    _MODELS_RESPONSE_KEY: ClassVar[str] = "data"
    _HEALTH_CHECK_PATH: ClassVar[str] = "v1/key"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        settings = get_settings()
        super().__init__(
            base_url=settings.OPENROUTER_BASE_URL,
            timeout=settings.UPSTREAM_TIMEOUT_SECONDS,
            client=client,
        )

    def is_rate_limited(self, response: httpx.Response) -> bool:
        return response.status_code == 429

    def is_key_exhausted(self, response: httpx.Response) -> bool:
        return response.status_code == 402
