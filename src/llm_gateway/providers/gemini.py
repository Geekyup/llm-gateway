from typing import ClassVar

import httpx

from llm_gateway.config import get_settings
from llm_gateway.providers.base import Provider


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
