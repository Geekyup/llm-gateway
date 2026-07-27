from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar

import httpx


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
