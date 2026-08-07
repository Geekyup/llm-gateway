import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, ClassVar

import httpx

from app.core.exceptions import ProviderRequestError

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class HealthCheckResult:
    ok: bool
    detail: str | None = None


class ModelInfo:
    __slots__ = ("label", "model_id")

    def __init__(self, model_id: str, label: str | None = None) -> None:
        self.model_id = model_id
        self.label = label or model_id


class Provider(ABC):
    name: ClassVar[str]

    @abstractmethod
    async def forward(
        self, *, key: str, path: str, method: str,
        payload: dict[str, Any] | None, headers: dict[str, str],
    ) -> httpx.Response:
        pass

    @abstractmethod
    def forward_stream(
        self, *, key: str, path: str, method: str,
        payload: dict[str, Any] | None, headers: dict[str, str],
    ):
        pass

    @abstractmethod
    def is_rate_limited(self, response: httpx.Response) -> bool:
        pass

    @abstractmethod
    def is_key_exhausted(self, response: httpx.Response) -> bool:
        pass

    @abstractmethod
    async def health_check(self, key: str) -> HealthCheckResult:
        pass

    @abstractmethod
    async def list_models(self, key: str) -> list[ModelInfo]:
        pass


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

    async def forward(
        self,
        *,
        key: str,
        path: str,
        method: str,
        payload: dict[str, Any] | None,
        headers: dict[str, str],
    ) -> httpx.Response:
        url = f"{self._base_url}/{path.lstrip('/')}"
        forward_headers = {
            k: v for k, v in headers.items()
            if k.lower() not in {"host", "content-length", "authorization"}
        }
        forward_headers.update(self._auth_headers(key))
        forward_headers.setdefault("content-type", "application/json")

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
        url = f"{self._base_url}/{path.lstrip('/')}"
        forward_headers = {
            k: v for k, v in headers.items()
            if k.lower() not in {"host", "content-length", "authorization"}
        }
        forward_headers.update(self._auth_headers(key))
        forward_headers.setdefault("content-type", "application/json")

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
        try:
            response = await self.forward(key=key, path=path, method="GET", payload=None, headers={})
        except httpx.HTTPError as exc:
            return HealthCheckResult(ok=False, detail=f"Network error: {exc}")

        if response.status_code == 200:
            return HealthCheckResult(ok=True)
        return HealthCheckResult(ok=False, detail=self._error_detail(response))

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
