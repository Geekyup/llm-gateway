from abc import ABC, abstractmethod
from typing import ClassVar

import httpx


class Provider(ABC):
    """Adapter to one upstream LLM API.

    Everything provider-specific (base URL, how the key is attached to the
    request, how to recognise a 429/quota-exhausted response) lives here so
    that gateway/keys code can stay entirely provider-agnostic.
    """

    name: ClassVar[str]

    @abstractmethod
    async def forward(self, *, key: str, path: str, method: str, payload: dict | None, headers: dict) -> httpx.Response:
        """Forward the request upstream using the given decrypted key. Never logs `key`."""

    @abstractmethod
    def is_rate_limited(self, response: httpx.Response) -> bool:
        """True if this response means 'this key is temporarily throttled, try another'."""

    @abstractmethod
    def is_key_exhausted(self, response: httpx.Response) -> bool:
        """True if this response means 'this key's quota is fully spent for the day/permanently'.

        Distinct from is_rate_limited: exhausted keys are parked until the
        next housekeeping reset (or manual admin action), cooldown keys
        recover on their own after `cooldown_seconds`.
        """
