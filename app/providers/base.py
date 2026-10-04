import logging
import re
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, ClassVar

import httpx

from app.core.exceptions import ProviderRequestError

logger = logging.getLogger(__name__)

_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9._:\-]+$")

OPENAI_COMPATIBLE_ROUTES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("POST", re.compile(r"v1/(?:chat/completions|completions|embeddings)")),
    ("GET", re.compile(r"v1/models(?:/.+)?")),
)


@dataclass(frozen=True, slots=True)
class HealthCheckResult:
    ok: bool
    detail: str | None = None
    latency_ms: int | None = None


class ModelInfo:
    __slots__ = ("label", "model_id")

    def __init__(self, model_id: str, label: str | None = None) -> None:
        self.model_id = model_id
        self.label = label or model_id


class Provider:
    name: ClassVar[str]
    ALLOWED_ROUTES: ClassVar[tuple[tuple[str, re.Pattern[str]], ...]] = ()

    def is_path_allowed(self, method: str, path: str) -> bool:
        segments = path.split("/")
        if any(seg in ("", ".", "..") or not _SAFE_SEGMENT.match(seg) for seg in segments):
            return False
        return any(
            allowed_method == method.upper() and pattern.fullmatch(path)
            for allowed_method, pattern in self.ALLOWED_ROUTES
        )

    async def forward(
        self, *, key: str, path: str, method: str,
        payload: dict[str, Any] | None, headers: dict[str, str],
    ) -> httpx.Response:
        raise NotImplementedError

    def forward_stream(
        self, *, key: str, path: str, method: str,
        payload: dict[str, Any] | None, headers: dict[str, str],
    ):
        raise NotImplementedError

    def is_rate_limited(self, response: httpx.Response) -> bool:
        raise NotImplementedError

    def is_key_exhausted(self, response: httpx.Response) -> bool:
        raise NotImplementedError

    def is_key_invalid(self, response: httpx.Response) -> bool:
        return False

    async def health_check(self, key: str) -> HealthCheckResult:
        raise NotImplementedError

    async def list_models(self, key: str) -> list[ModelInfo]:
        raise NotImplementedError


class HTTPProvider(Provider):
    _MODELS_PATH: ClassVar[str]
    _HEALTH_CHECK_PATH: ClassVar[str] = ""
    _MODELS_RESPONSE_KEY: ClassVar[str] = "data"

    def __init__(self, *, base_url: str, timeout: float, client: httpx.AsyncClient | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client = client

    def _auth_headers(self, key: str) -> dict[str, str]:
        return {"authorization": f"Bearer {key}"}

    def _build_request(self, key: str, path: str, headers: dict[str, str]) -> tuple[str, dict[str, str]]:
        url = f"{self._base_url}/{path.lstrip('/')}"
        forward_headers = {
            k: v for k, v in headers.items()
            if k.lower() not in {"host", "content-length", "authorization"}
        }
        forward_headers.update(self._auth_headers(key))
        forward_headers.setdefault("content-type", "application/json")
        return url, forward_headers

    async def forward(
        self,
        *,
        key: str,
        path: str,
        method: str,
        payload: dict[str, Any] | None,
        headers: dict[str, str],
    ) -> httpx.Response:
        url, forward_headers = self._build_request(key, path, headers)

        client = self._client or httpx.AsyncClient(timeout=self._timeout)
        try:
            return await client.request(method, url, json=payload, headers=forward_headers)
        finally:
            if self._client is None:
                await client.aclose()

    @asynccontextmanager
    async def forward_stream(
        self,
        *,
        key: str,
        path: str,
        method: str,
        payload: dict[str, Any] | None,
        headers: dict[str, str],
    ) -> AsyncIterator[httpx.Response]:
        url, forward_headers = self._build_request(key, path, headers)

        client = self._client or httpx.AsyncClient(timeout=self._timeout)
        try:
            async with client.stream(method, url, json=payload, headers=forward_headers) as response:
                yield response
        finally:
            if self._client is None:
                await client.aclose()

    def _error_detail(self, response: httpx.Response) -> str:
        detail = f"HTTP {response.status_code}"
        try:
            message = response.json().get("error", {}).get("message")
            if message:
                detail = f"{detail}: {message}"
        except Exception:
            logger.debug("failed to parse error detail from response body", exc_info=True)
        return detail

    async def health_check(self, key: str) -> HealthCheckResult:
        path = self._HEALTH_CHECK_PATH or self._MODELS_PATH
        started = time.monotonic()
        try:
            response = await self.forward(key=key, path=path, method="GET", payload=None, headers={})
        except httpx.HTTPError as exc:
            return HealthCheckResult(ok=False, detail=f"Network error: {exc}")
        latency_ms = int((time.monotonic() - started) * 1000)

        if response.status_code == 200:
            return HealthCheckResult(ok=True, latency_ms=latency_ms)
        return HealthCheckResult(ok=False, detail=self._error_detail(response), latency_ms=latency_ms)

    async def list_models(self, key: str) -> list[ModelInfo]:
        try:
            response = await self.forward(key=key, path=self._MODELS_PATH, method="GET", payload=None, headers={})
        except httpx.HTTPError as exc:
            raise ProviderRequestError(provider=self.name, reason=f"Network error: {exc}") from exc

        if response.status_code != 200:
            raise ProviderRequestError(provider=self.name, reason=self._error_detail(response))

        body = response.json()
        return self._parse_models(body)

    def _parse_models(self, body: dict) -> list[ModelInfo]:
        models = []
        for entry in body.get(self._MODELS_RESPONSE_KEY, []):
            model_id = entry.get("id")
            if not model_id:
                continue
            models.append(ModelInfo(model_id=model_id, label=entry.get("name") or model_id))
        return models