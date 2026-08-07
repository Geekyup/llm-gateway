import logging
from typing import ClassVar

import httpx

from app.config import get_settings
from app.providers.base import HTTPProvider, ModelInfo

logger = logging.getLogger(__name__)

_QUOTA_EXHAUSTED_STATUSES = {"RESOURCE_EXHAUSTED"}


class GeminiProvider(HTTPProvider):
    name: ClassVar[str] = "gemini"
    _MODELS_PATH: ClassVar[str] = "v1beta/models"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        settings = get_settings()
        super().__init__(
            base_url=settings.GEMINI_BASE_URL,
            timeout=settings.UPSTREAM_TIMEOUT_SECONDS,
            client=client,
        )

    def _auth_headers(self, key: str) -> dict[str, str]:
        return {"x-goog-api-key": key}

    def is_rate_limited(self, response: httpx.Response) -> bool:
        return response.status_code == 429

    def is_key_exhausted(self, response: httpx.Response) -> bool:
        if response.status_code != 403:
            return False
        try:
            status = response.json().get("error", {}).get("status")
        except Exception:
            logger.debug("failed to parse error body while checking exhaustion", exc_info=True)
            return False
        return status in _QUOTA_EXHAUSTED_STATUSES

    def _parse_models(self, body: dict) -> list[ModelInfo]:
        models = []
        for entry in body.get("models", []):
            raw_name = entry.get("name", "")
            model_id = raw_name.removeprefix("models/")
            if not model_id:
                continue

            supported = entry.get("supportedGenerationMethods", [])
            if "generateContent" not in supported:
                continue
            models.append(ModelInfo(model_id=model_id, label=entry.get("displayName")))
        return models
