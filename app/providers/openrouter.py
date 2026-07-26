from typing import ClassVar

import httpx

from app.config import get_settings
from app.core.exceptions import ProviderRequestError
from app.providers.base import HealthCheckResult, ModelInfo, Provider


class OpenRouterProvider(Provider):
    """Adapter for OpenRouter (https://openrouter.ai).

    Unlike Gemini, OpenRouter's API is already OpenAI-compatible — the
    same request/response shape our /v1/chat/completions endpoint accepts
    from clients. So `path`/`payload` here are expected to already be in
    OpenAI chat-completions form and are forwarded close to 1:1, with no
    Gemini-style request/response translation needed.
    """

    name: ClassVar[str] = "openrouter"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        settings = get_settings()
        self._base_url = settings.OPENROUTER_BASE_URL.rstrip("/")
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
        forward_headers = {k: v for k, v in headers.items() if k.lower() not in {"host", "content-length", "authorization"}}
        forward_headers["authorization"] = f"Bearer {key}"
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
        # OpenRouter returns 402 Payment Required when the account is out
        # of credits — the closest equivalent to Gemini's "permanently
        # exhausted" 403. Distinct from 429 (temporary throttle, recovers
        # on its own): 402 means the key needs a human to add funds, so it
        # should be parked rather than retried on a cooldown timer.
        return response.status_code == 402

    async def health_check(self, key: str) -> HealthCheckResult:
        # GET /api/v1/key returns the calling key's own credit/rate-limit
        # info — authenticated, but doesn't run a completion, so it's free
        # and doesn't touch generation quota.
        try:
            response = await self.forward(key=key, path="v1/key", method="GET", payload=None, headers={})
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
        except Exception:  # noqa: BLE001 - best-effort detail extraction only
            pass
        return HealthCheckResult(ok=False, detail=detail)

    async def list_models(self, key: str) -> list[ModelInfo]:
        # GET /api/v1/models is actually a public, unauthenticated catalog
        # of every model on the platform (not filtered to what this key
        # can afford/access) — OpenRouter doesn't offer a per-key model
        # list. We still send the key so this fails the same way other
        # calls would if it were ever revoked, and so a future
        # personalized-list endpoint would just work here without callers
        # changing.
        try:
            response = await self.forward(key=key, path="v1/models", method="GET", payload=None, headers={})
        except httpx.HTTPError as exc:
            raise ProviderRequestError(provider=self.name, reason=f"Network error: {exc}") from exc

        if response.status_code != 200:
            reason = f"HTTP {response.status_code}"
            try:
                message = response.json().get("error", {}).get("message")
                if message:
                    reason = f"HTTP {response.status_code}: {message}"
            except Exception:  # noqa: BLE001 - best-effort detail extraction only
                pass
            raise ProviderRequestError(provider=self.name, reason=reason)

        body = response.json()
        models = []
        for entry in body.get("data", []):
            model_id = entry.get("id")
            if not model_id:
                continue
            models.append(ModelInfo(id=model_id, label=entry.get("name")))
        return models
