import httpx
import pytest

from llm_gateway.core.exceptions import NoAvailableKeysError, UpstreamExhaustedError
from llm_gateway.gateway.proxy_service import GatewayService
from llm_gateway.keys.cache import KeyStatusCache
from llm_gateway.keys.enums import ProviderType
from llm_gateway.keys.selector import RoundRobinSelector
from llm_gateway.keys.service import KeyPoolService


class ScriptedProvider:
    """Fake Provider that returns a scripted sequence of status codes,
    one per call, regardless of which key was used — lets tests assert
    on failover behaviour without hitting a real upstream.
    """

    def __init__(self, status_codes: list[int]) -> None:
        self._status_codes = iter(status_codes)
        self.calls: list[str] = []

    async def forward(self, *, key, path, method, payload, headers):
        self.calls.append(key)
        status = next(self._status_codes)
        return httpx.Response(status_code=status, json={"ok": status == 200})

    def is_rate_limited(self, response: httpx.Response) -> bool:
        return response.status_code == 429

    def is_key_exhausted(self, response: httpx.Response) -> bool:
        return response.status_code == 403


@pytest.fixture
def key_pool(key_repo, fake_redis):
    cache = KeyStatusCache(fake_redis, ttl_seconds=30)
    selector = RoundRobinSelector(fake_redis)
    return KeyPoolService(key_repo, cache, selector)


async def _create_active_key(key_pool: KeyPoolService, label: str):
    from llm_gateway.keys.schemas import APIKeyCreate

    return await key_pool.create_key(
        APIKeyCreate(label=label, provider=ProviderType.GEMINI, raw_key=f"raw-{label}", daily_limit=100)
    )


@pytest.mark.asyncio
async def test_first_key_succeeds_no_retry(key_pool):
    await _create_active_key(key_pool, "k1")
    provider = ScriptedProvider([200])
    gateway = GatewayService(key_pool, max_attempts=3)

    response = await gateway.proxy_request(
        provider=provider,
        provider_type=ProviderType.GEMINI,
        path="v1beta/models/gemini-1.5-flash:generateContent",
        method="POST",
        payload={"hello": "world"},
        headers={},
    )

    assert response.status_code == 200
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_429_triggers_failover_to_second_key(key_pool):
    await _create_active_key(key_pool, "k1")
    await _create_active_key(key_pool, "k2")
    provider = ScriptedProvider([429, 200])
    gateway = GatewayService(key_pool, max_attempts=3)

    response = await gateway.proxy_request(
        provider=provider,
        provider_type=ProviderType.GEMINI,
        path="p",
        method="POST",
        payload=None,
        headers={},
    )

    assert response.status_code == 200
    assert len(provider.calls) == 2
    # The two calls must have used different decrypted keys.
    assert provider.calls[0] != provider.calls[1]


@pytest.mark.asyncio
async def test_all_keys_rate_limited_raises_upstream_exhausted(key_pool):
    await _create_active_key(key_pool, "k1")
    await _create_active_key(key_pool, "k2")
    provider = ScriptedProvider([429, 429])
    gateway = GatewayService(key_pool, max_attempts=3)

    with pytest.raises(UpstreamExhaustedError):
        await gateway.proxy_request(
            provider=provider,
            provider_type=ProviderType.GEMINI,
            path="p",
            method="POST",
            payload=None,
            headers={},
        )


@pytest.mark.asyncio
async def test_no_keys_at_all_raises_no_available_keys(key_pool):
    provider = ScriptedProvider([])
    gateway = GatewayService(key_pool, max_attempts=3)

    with pytest.raises(NoAvailableKeysError):
        await gateway.proxy_request(
            provider=provider,
            provider_type=ProviderType.GEMINI,
            path="p",
            method="POST",
            payload=None,
            headers={},
        )


@pytest.mark.asyncio
async def test_exhausted_key_marked_and_skipped_next_call(key_pool):
    await _create_active_key(key_pool, "k1")
    await _create_active_key(key_pool, "k2")
    provider = ScriptedProvider([403, 200])
    gateway = GatewayService(key_pool, max_attempts=3)

    response = await gateway.proxy_request(
        provider=provider,
        provider_type=ProviderType.GEMINI,
        path="p",
        method="POST",
        payload=None,
        headers={},
    )

    assert response.status_code == 200
    # Round-robin cursor start isn't fixed to k1, so assert on counts rather
    # than which specific label got exhausted: exactly one key should have
    # been marked exhausted (the one that returned 403) and one should
    # remain active (the one that returned 200 on the retry).
    keys = await key_pool.list_keys(provider=ProviderType.GEMINI)
    statuses = sorted(k.status.value for k in keys)
    assert statuses == ["active", "exhausted"]
