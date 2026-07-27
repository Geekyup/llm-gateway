import logging
from typing import ClassVar

import httpx

from app.config import get_settings
from app.core.exceptions import ProviderRequestError
from app.providers.base import HealthCheckResult, ModelInfo, Provider

logger = logging.getLogger(__name__)


class GeminiProvider(Provider):
    name: ClassVar[str] = "gemini"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        settings = get_settings()
        self._base_url = settings.GEMINI_BASE_URL.rstrip("/")
        self._timeout = settings.UPSTREAM_TIMEOUT_SECONDS
        self._client = client

    async def forward(
        self,
        *,
        key: str,
        path: str,
        method: str,
        payload: dict | None,
        headers: dict,
    ) -> httpx.Response:
        url = f"{self._base_url}/{path.lstrip('/')}"
        forward_headers = {k: v for k, v in headers.items() if k.lower() not in {"host", "content-length", "authorization"}}
        forward_headers["x-goog-api-key"] = key
        forward_headers.setdefault("content-type", "application/json")

        client = self._client or httpx.AsyncClient(timeout=self._timeout)
        try:
            return await client.request(method, url, json=payload, headers=forward_headers)
        finally:
            if self._client is None:
                await client.aclose()

    def is_rate_limited(self, response: httpx.Response) -> bool:
        return response.status_code == 429

    def is_key_exhausted(self, response: httpx.Response) -> bool:
        return response.status_code == 403

    async def health_check(self, key: str) -> HealthCheckResult:
        try:
            response = await self.forward(key=key, path="v1beta/models", method="GET", payload=None, headers={})
        except httpx.HTTPError as exc:
            return HealthCheckResult(ok=False, detail=f"Network error: {exc}")

        if response.status_code == 200:
            return HealthCheckResult(ok=True)

        detail = f"HTTP {response.status_code}"
        try:
            body = response.json()
            message = body.get("error", {}).get("message")
            if message:
                detail = f"HTTP {response.status_code}: {message}"
        except Exception:
            logger.debug("failed to parse error detail from response body", exc_info=True)
        return HealthCheckResult(ok=False, detail=detail)

    async def list_models(self, key: str) -> list[ModelInfo]:
        try:
            response = await self.forward(key=key, path="v1beta/models", method="GET", payload=None, headers={})
        except httpx.HTTPError as exc:
            raise ProviderRequestError(provider=self.name, reason=f"Network error: {exc}") from exc

        if response.status_code != 200:
            detail = f"HTTP {response.status_code}"
            try:
                message = response.json().get("error", {}).get("message")
                if message:
                    detail = f"HTTP {response.status_code}: {message}"
            except Exception:
                logger.debug("failed to parse error detail from response body", exc_info=True)
            raise ProviderRequestError(provider=self.name, reason=detail)

        body = response.json()
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
