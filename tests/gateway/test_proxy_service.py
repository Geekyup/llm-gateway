import httpx
import pytest

from app.core.exceptions import NoAvailableKeysError, UpstreamExhaustedError
from app.gateway.proxy_service import GatewayService
from app.keys.cache import KeyStatusCache
from app.keys.enums import ProviderType
from app.keys.selector import RoundRobinSelector
from app.keys.service import KeyPoolService
from app.monitoring.publisher import RequestEventPublisher


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


class UsageMetadataProvider:
    """Fake Provider returning a Gemini-shaped 200 with usageMetadata, to
    test token accounting without hitting a real upstream.
    """

    def __init__(self, usage_metadata: dict | None = None) -> None:
        self._usage_metadata = usage_metadata

    async def forward(self, *, key, path, method, payload, headers):
        body = {"candidates": []}
        if self._usage_metadata is not None:
            body["usageMetadata"] = self._usage_metadata
        return httpx.Response(status_code=200, json=body)

    def is_rate_limited(self, response: httpx.Response) -> bool:
        return response.status_code == 429

    def is_key_exhausted(self, response: httpx.Response) -> bool:
        return response.status_code == 403


@pytest.fixture
def key_pool(key_repo, fake_redis):
    cache = KeyStatusCache(fake_redis, ttl_seconds=30)
    selector = RoundRobinSelector(fake_redis)
    return KeyPoolService(key_repo, cache, selector)


async def _create_active_key(key_pool: KeyPoolService, user_id: int, label: str):
    from app.keys.schemas import APIKeyCreate

    return await key_pool.create_key(
        user_id, APIKeyCreate(label=label, provider=ProviderType.GEMINI, raw_key=f"raw-{label}", daily_limit=100)
    )


@pytest.mark.asyncio
async def test_first_key_succeeds_no_retry(key_pool, test_user):
    await _create_active_key(key_pool, test_user.id, "k1")
    provider = ScriptedProvider([200])
    gateway = GatewayService(key_pool, max_attempts=3)

    response = await gateway.proxy_request(
        user_id=test_user.id,
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
async def test_429_triggers_failover_to_second_key(key_pool, test_user):
    await _create_active_key(key_pool, test_user.id, "k1")
    await _create_active_key(key_pool, test_user.id, "k2")
    provider = ScriptedProvider([429, 200])
    gateway = GatewayService(key_pool, max_attempts=3)

    response = await gateway.proxy_request(
        user_id=test_user.id,
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
async def test_all_keys_rate_limited_raises_upstream_exhausted(key_pool, test_user):
    await _create_active_key(key_pool, test_user.id, "k1")
    await _create_active_key(key_pool, test_user.id, "k2")
    provider = ScriptedProvider([429, 429])
    gateway = GatewayService(key_pool, max_attempts=3)

    with pytest.raises(UpstreamExhaustedError):
        await gateway.proxy_request(
            user_id=test_user.id,
            provider=provider,
            provider_type=ProviderType.GEMINI,
            path="p",
            method="POST",
            payload=None,
            headers={},
        )


@pytest.mark.asyncio
async def test_no_keys_at_all_raises_no_available_keys(key_pool, test_user):
    provider = ScriptedProvider([])
    gateway = GatewayService(key_pool, max_attempts=3)

    with pytest.raises(NoAvailableKeysError):
        await gateway.proxy_request(
            user_id=test_user.id,
            provider=provider,
            provider_type=ProviderType.GEMINI,
            path="p",
            method="POST",
            payload=None,
            headers={},
        )


@pytest.mark.asyncio
async def test_exhausted_key_marked_and_skipped_next_call(key_pool, test_user):
    await _create_active_key(key_pool, test_user.id, "k1")
    await _create_active_key(key_pool, test_user.id, "k2")
    provider = ScriptedProvider([403, 200])
    gateway = GatewayService(key_pool, max_attempts=3)

    response = await gateway.proxy_request(
        user_id=test_user.id,
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
    keys = await key_pool.list_keys(test_user.id, provider=ProviderType.GEMINI)
    statuses = sorted(k.status.value for k in keys)
    assert statuses == ["active", "exhausted"]


@pytest.mark.asyncio
async def test_user_never_draws_on_another_users_keys(key_pool, test_user, other_user):
    """The core isolation guarantee: a request authenticated as test_user
    must only ever be served by test_user's own keys, even when another
    user's pool has active keys for the same provider.
    """
    await _create_active_key(key_pool, other_user.id, "not-yours")
    provider = ScriptedProvider([])
    gateway = GatewayService(key_pool, max_attempts=3)

    # test_user has zero keys of their own — must fail with NoAvailableKeysError,
    # never silently fall back to other_user's key.
    with pytest.raises(NoAvailableKeysError):
        await gateway.proxy_request(
            user_id=test_user.id,
            provider=provider,
            provider_type=ProviderType.GEMINI,
            path="p",
            method="POST",
            payload=None,
            headers={},
        )
    assert provider.calls == []


@pytest.mark.asyncio
async def test_successful_request_emits_one_event(key_pool, fake_redis, test_user):
    await _create_active_key(key_pool, test_user.id, "k1")
    provider = ScriptedProvider([200])
    publisher = RequestEventPublisher(fake_redis)
    gateway = GatewayService(key_pool, max_attempts=3, event_publisher=publisher)

    await gateway.proxy_request(
        user_id=test_user.id,
        provider=provider,
        provider_type=ProviderType.GEMINI,
        path="p",
        method="POST",
        payload=None,
        headers={},
    )

    events = await publisher.recent(test_user.id, limit=10)
    assert len(events) == 1
    assert events[0].outcome == "success"
    assert events[0].attempt == 1
    assert events[0].is_retry is False
    assert events[0].upstream_status == 200
    assert events[0].user_id == test_user.id


@pytest.mark.asyncio
async def test_retry_emits_one_event_per_attempt_sharing_request_id(key_pool, fake_redis, test_user):
    await _create_active_key(key_pool, test_user.id, "k1")
    await _create_active_key(key_pool, test_user.id, "k2")
    provider = ScriptedProvider([429, 200])
    publisher = RequestEventPublisher(fake_redis)
    gateway = GatewayService(key_pool, max_attempts=3, event_publisher=publisher)

    await gateway.proxy_request(
        user_id=test_user.id,
        provider=provider,
        provider_type=ProviderType.GEMINI,
        path="p",
        method="POST",
        payload=None,
        headers={},
    )

    events = await publisher.recent(test_user.id, limit=10)
    assert len(events) == 2
    # recent() returns newest first: attempt 2 (success) then attempt 1 (rate_limited).
    assert events[0].outcome == "success"
    assert events[0].attempt == 2
    assert events[0].is_retry is True
    assert events[1].outcome == "rate_limited"
    assert events[1].attempt == 1
    assert events[1].is_retry is False
    # Both hops of the same client request share one request_id.
    assert events[0].request_id == events[1].request_id


@pytest.mark.asyncio
async def test_no_keys_available_emits_no_keys_event(key_pool, fake_redis, test_user):
    provider = ScriptedProvider([])
    publisher = RequestEventPublisher(fake_redis)
    gateway = GatewayService(key_pool, max_attempts=3, event_publisher=publisher)

    with pytest.raises(NoAvailableKeysError):
        await gateway.proxy_request(
            user_id=test_user.id,
            provider=provider,
            provider_type=ProviderType.GEMINI,
            path="p",
            method="POST",
            payload=None,
            headers={},
        )

    events = await publisher.recent(test_user.id, limit=10)
    assert len(events) == 1
    assert events[0].outcome == "no_keys"
    assert events[0].key_id is None


@pytest.mark.asyncio
async def test_events_never_leak_across_users(key_pool, fake_redis, test_user, other_user):
    """Two users hitting the gateway concurrently must never see each
    other's events in their own history.
    """
    await _create_active_key(key_pool, test_user.id, "mine")
    await _create_active_key(key_pool, other_user.id, "theirs")
    publisher = RequestEventPublisher(fake_redis)
    gateway = GatewayService(key_pool, max_attempts=3, event_publisher=publisher)

    await gateway.proxy_request(
        user_id=test_user.id,
        provider=ScriptedProvider([200]),
        provider_type=ProviderType.GEMINI,
        path="p",
        method="POST",
        payload=None,
        headers={},
    )
    await gateway.proxy_request(
        user_id=other_user.id,
        provider=ScriptedProvider([200]),
        provider_type=ProviderType.GEMINI,
        path="p",
        method="POST",
        payload=None,
        headers={},
    )

    my_events = await publisher.recent(test_user.id, limit=10)
    their_events = await publisher.recent(other_user.id, limit=10)
    assert len(my_events) == 1
    assert len(their_events) == 1
    assert my_events[0].user_id == test_user.id
    assert their_events[0].user_id == other_user.id


@pytest.mark.asyncio
async def test_no_publisher_configured_does_not_raise(key_pool, test_user):
    """GatewayService without an event_publisher (e.g. old test call sites)
    must keep working exactly as before — monitoring is additive, not required.
    """
    await _create_active_key(key_pool, test_user.id, "k1")
    provider = ScriptedProvider([200])
    gateway = GatewayService(key_pool, max_attempts=3)  # no event_publisher

    response = await gateway.proxy_request(
        user_id=test_user.id,
        provider=provider,
        provider_type=ProviderType.GEMINI,
        path="p",
        method="POST",
        payload=None,
        headers={},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_successful_request_captures_token_usage(key_pool, fake_redis, test_user):
    await _create_active_key(key_pool, test_user.id, "k1")
    provider = UsageMetadataProvider({"promptTokenCount": 120, "candidatesTokenCount": 45, "totalTokenCount": 165})
    publisher = RequestEventPublisher(fake_redis)
    gateway = GatewayService(key_pool, max_attempts=3, event_publisher=publisher)

    await gateway.proxy_request(
        user_id=test_user.id,
        provider=provider,
        provider_type=ProviderType.GEMINI,
        path="p",
        method="POST",
        payload=None,
        headers={},
    )

    events = await publisher.recent(test_user.id, limit=10)
    assert len(events) == 1
    assert events[0].prompt_tokens == 120
    assert events[0].completion_tokens == 45
    assert events[0].total_tokens == 165


@pytest.mark.asyncio
async def test_missing_usage_metadata_does_not_raise(key_pool, fake_redis, test_user):
    """Not every upstream response includes usageMetadata (e.g. errors that
    still return 200, or a provider that omits it) — token fields should
    just come back None rather than breaking the request.
    """
    await _create_active_key(key_pool, test_user.id, "k1")
    provider = UsageMetadataProvider(usage_metadata=None)
    publisher = RequestEventPublisher(fake_redis)
    gateway = GatewayService(key_pool, max_attempts=3, event_publisher=publisher)

    response = await gateway.proxy_request(
        user_id=test_user.id,
        provider=provider,
        provider_type=ProviderType.GEMINI,
        path="p",
        method="POST",
        payload=None,
        headers={},
    )

    assert response.status_code == 200
    events = await publisher.recent(test_user.id, limit=10)
    assert events[0].prompt_tokens is None
    assert events[0].completion_tokens is None
    assert events[0].total_tokens is None
