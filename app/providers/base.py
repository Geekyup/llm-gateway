from abc import ABC, abstractmethod
from typing import ClassVar

import httpx


class HealthCheckResult:
    """Outcome of a single Provider.health_check call.

    `ok` is the simple yes/no an admin cares about; `detail` is a short,
    human-readable reason (never includes the key itself) for the cases
    where `ok` is False, e.g. "HTTP 401: API key not valid".
    """

    __slots__ = ("ok", "detail")

    def __init__(self, ok: bool, detail: str | None = None) -> None:
        self.ok = ok
        self.detail = detail


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

    @abstractmethod
    async def health_check(self, key: str) -> HealthCheckResult:
        """Make a cheap, quota-friendly call to verify the key actually works.

        Unlike is_rate_limited/is_key_exhausted (which classify a response
        that already happened as part of real client traffic), this makes
        its own lightweight request on demand — e.g. for an admin "Test"
        button or a periodic sweep — and should avoid billed/heavy
        endpoints (no completions/generation calls).
        """
