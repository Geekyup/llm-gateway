import logging
from typing import ClassVar

import httpx

from app.config import get_settings
from app.core.exceptions import ProviderRequestError
from app.providers.base import HealthCheckResult, ModelInfo, Provider

logger = logging.getLogger(__name__)


class GeminiProvider(Provider):
    """Adapter for the Google Generative Language (Gemini) API.

    MVP forwards requests 1:1 (path + body pass-through) — no OpenAI-format
    normalization yet. `path` is expected to already be the Gemini-style
    suffix, e.g. "v1beta/models/gemini-1.5-flash:generateContent".
    """

    name: ClassVar[str] = "gemini"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        settings = get_settings()
        self._base_url = settings.GEMINI_BASE_URL.rstrip("/")
        self._timeout = settings.UPSTREAM_TIMEOUT_SECONDS
        # Allow injecting a client (tests / connection reuse); otherwise
        # build a short-lived one per call — fine for MVP traffic levels.
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
        # Gemini accepts the API key either as ?key= or x-goog-api-key header;
        # header avoids the key ending up in access logs / URL-based caches.
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
        # Gemini doesn't have a distinct "permanently exhausted" status code
        # in the free tier — 403 with PERMISSION_DENIED/quota language is
        # the closest signal. Treated conservatively: only explicit 403.
        return response.status_code == 403

    async def health_check(self, key: str) -> HealthCheckResult:
        # GET v1beta/models just lists available models — it's authenticated
        # by the key but doesn't run a generation, so it doesn't touch the
        # per-key request quota the way generateContent would.
        try:
            response = await self.forward(key=key, path="v1beta/models", method="GET", payload=None, headers={})
        except httpx.HTTPError as exc:
            return HealthCheckResult(ok=False, detail=f"Network error: {exc}")

        if response.status_code == 200:
            return HealthCheckResult(ok=True)

        # Pull Gemini's structured error message when present, e.g.
        # {"error": {"message": "API key not valid. Please pass a valid API key."}}
        # rather than dumping the raw (possibly large/HTML) body.
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
            # entry["name"] is like "models/gemini-3.6-flash" — strip the
            # "models/" prefix since that's the id clients actually send
            # as ChatCompletionRequest.model and what a key gets pinned to.
            raw_name = entry.get("name", "")
            model_id = raw_name.removeprefix("models/")
            if not model_id:
                continue
            # Only list models that support the call this gateway actually
            # makes — generateContent — so the picker doesn't offer e.g.
            # embedding-only models that would just 404 on every request.
            supported = entry.get("supportedGenerationMethods", [])
            if "generateContent" not in supported:
                continue
            models.append(ModelInfo(id=model_id, label=entry.get("displayName")))
        return models
