import httpx
import pytest

from app.core.exceptions import NoAvailableKeysError, UpstreamExhaustedError
from app.gateway.proxy_service import GatewayService, UpstreamRequestSpec
from app.keys.cache import KeyStatusCache
from app.keys.enums import ProviderType
from app.keys.selector import RoundRobinSelector
from app.keys.service import KeyPoolService
from app.monitoring.publisher import RequestEventPublisher


class ScriptedProvider:
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


class ScriptedStreamProvider:
    
    def __init__(self, status_codes: list[int], bodies: list[bytes] | None = None) -> None:
        self._status_codes = iter(status_codes)
        self._bodies = iter(bodies or [])
        self.calls: list[str] = []

    def forward_stream(self, *, key, path, method, payload, headers):
        self.calls.append(key)
        status = next(self._status_codes)
        try:
            body = next(self._bodies)
        except StopIteration:
            body = b'{"ok": true}'
        response = httpx.Response(status_code=status, content=body, request=httpx.Request(method, f"http://upstream/{path}"))
        return _FakeStreamContext(response)

    def is_rate_limited(self, response: httpx.Response) -> bool:
        return response.status_code == 429

    def is_key_exhausted(self, response: httpx.Response) -> bool:
        return response.status_code == 403


class _FakeStreamContext:
    def __init__(self, response: httpx.Response) -> None:
        self._response = response

    async def __aenter__(self) -> httpx.Response:
        return self._response

    async def __aexit__(self, *exc_info) -> None:
        return None


@pytest.fixture
def key_pool(key_repo, fake_redis):
    cache = KeyStatusCache(fake_redis, ttl_seconds=30)
    selector = RoundRobinSelector(fake_redis)
    return KeyPoolService(key_repo, cache, selector)


@pytest.fixture(autouse=True)
def _patch_registry(monkeypatch):
    state = {"provider": None}

    def fake_get_provider(name: str):
        assert state["provider"] is not None, "call _use_provider(monkeypatch, provider) before proxy_request"
        return state["provider"]

    monkeypatch.setattr("app.gateway.proxy_service.get_provider", fake_get_provider)

    def _use(provider):
        state["provider"] = provider

    return _use


async def _create_active_key(key_pool: KeyPoolService, user_id: int, label: str, model: str | None = None):
    from app.keys.schemas import APIKeyCreate

    return await key_pool.create_key(
        user_id,
        APIKeyCreate(label=label, provider=ProviderType.GEMINI, raw_key=f"raw-{label}", daily_limit=100, model=model),
    )


def _build_request(path="p", payload=None, headers=None):
    def build(_dto):
        return UpstreamRequestSpec(path=path, method="POST", payload=payload, headers=headers or {})
    return build


@pytest.mark.asyncio
async def test_first_key_succeeds_no_retry(key_pool, test_user, _patch_registry):
    await _create_active_key(key_pool, test_user.id, "k1")
    provider = ScriptedProvider([200])
    _patch_registry(provider)
    gateway = GatewayService(key_pool, max_attempts=3)

    response = await gateway.proxy_request(
        user_id=test_user.id,
        build_request=_build_request(path="v1beta/models/gemini-1.5-flash:generateContent", payload={"hello": "world"}),
        provider_type=ProviderType.GEMINI,
    )

    assert response.status_code == 200
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_429_triggers_failover_to_second_key(key_pool, test_user, _patch_registry):
    await _create_active_key(key_pool, test_user.id, "k1")
    await _create_active_key(key_pool, test_user.id, "k2")
    provider = ScriptedProvider([429, 200])
    _patch_registry(provider)
    gateway = GatewayService(key_pool, max_attempts=3)

    response = await gateway.proxy_request(
        user_id=test_user.id,
        build_request=_build_request(),
        provider_type=ProviderType.GEMINI,
    )

    assert response.status_code == 200
    assert len(provider.calls) == 2
    assert provider.calls[0] != provider.calls[1]


@pytest.mark.asyncio
async def test_all_keys_rate_limited_raises_upstream_exhausted(key_pool, test_user, _patch_registry):
    await _create_active_key(key_pool, test_user.id, "k1")
    await _create_active_key(key_pool, test_user.id, "k2")
    provider = ScriptedProvider([429, 429])
    _patch_registry(provider)
    gateway = GatewayService(key_pool, max_attempts=3)

    with pytest.raises(UpstreamExhaustedError):
        await gateway.proxy_request(
            user_id=test_user.id,
            build_request=_build_request(),
            provider_type=ProviderType.GEMINI,
        )


@pytest.mark.asyncio
async def test_no_keys_at_all_raises_no_available_keys(key_pool, test_user, _patch_registry):
    provider = ScriptedProvider([])
    _patch_registry(provider)
    gateway = GatewayService(key_pool, max_attempts=3)

    with pytest.raises(NoAvailableKeysError):
        await gateway.proxy_request(
            user_id=test_user.id,
            build_request=_build_request(),
            provider_type=ProviderType.GEMINI,
        )


@pytest.mark.asyncio
async def test_exhausted_key_marked_and_skipped_next_call(key_pool, test_user, _patch_registry):
    await _create_active_key(key_pool, test_user.id, "k1")
    await _create_active_key(key_pool, test_user.id, "k2")
    provider = ScriptedProvider([403, 200])
    _patch_registry(provider)
    gateway = GatewayService(key_pool, max_attempts=3)

    response = await gateway.proxy_request(
        user_id=test_user.id,
        build_request=_build_request(),
        provider_type=ProviderType.GEMINI,
    )

    assert response.status_code == 200
    keys = await key_pool.list_keys(test_user.id, provider=ProviderType.GEMINI)
    statuses = sorted(k.status.value for k in keys)
    assert statuses == ["active", "exhausted"]


@pytest.mark.asyncio
async def test_user_never_draws_on_another_users_keys(key_pool, test_user, other_user, _patch_registry):
    await _create_active_key(key_pool, other_user.id, "not-yours")
    provider = ScriptedProvider([])
    _patch_registry(provider)
    gateway = GatewayService(key_pool, max_attempts=3)

    with pytest.raises(NoAvailableKeysError):
        await gateway.proxy_request(
            user_id=test_user.id,
            build_request=_build_request(),
            provider_type=ProviderType.GEMINI,
        )
    assert provider.calls == []


@pytest.mark.asyncio
async def test_successful_request_emits_one_event(key_pool, fake_redis, test_user, _patch_registry):
    await _create_active_key(key_pool, test_user.id, "k1")
    provider = ScriptedProvider([200])
    _patch_registry(provider)
    publisher = RequestEventPublisher(fake_redis)
    gateway = GatewayService(key_pool, max_attempts=3, event_publisher=publisher)

    await gateway.proxy_request(
        user_id=test_user.id,
        build_request=_build_request(),
        provider_type=ProviderType.GEMINI,
    )

    events = await publisher.recent(test_user.id, limit=10)
    assert len(events) == 1
    assert events[0].outcome == "success"
    assert events[0].attempt == 1
    assert events[0].is_retry is False
    assert events[0].upstream_status == 200
    assert events[0].user_id == test_user.id


@pytest.mark.asyncio
async def test_retry_emits_one_event_per_attempt_sharing_request_id(key_pool, fake_redis, test_user, _patch_registry):
    await _create_active_key(key_pool, test_user.id, "k1")
    await _create_active_key(key_pool, test_user.id, "k2")
    provider = ScriptedProvider([429, 200])
    _patch_registry(provider)
    publisher = RequestEventPublisher(fake_redis)
    gateway = GatewayService(key_pool, max_attempts=3, event_publisher=publisher)

    await gateway.proxy_request(
        user_id=test_user.id,
        build_request=_build_request(),
        provider_type=ProviderType.GEMINI,
    )

    events = await publisher.recent(test_user.id, limit=10)
    assert len(events) == 2
    assert events[0].outcome == "success"
    assert events[0].attempt == 2
    assert events[0].is_retry is True
    assert events[1].outcome == "rate_limited"
    assert events[1].attempt == 1
    assert events[1].is_retry is False
    assert events[0].request_id == events[1].request_id


@pytest.mark.asyncio
async def test_no_keys_available_emits_no_keys_event(key_pool, fake_redis, test_user, _patch_registry):
    provider = ScriptedProvider([])
    _patch_registry(provider)
    publisher = RequestEventPublisher(fake_redis)
    gateway = GatewayService(key_pool, max_attempts=3, event_publisher=publisher)

    with pytest.raises(NoAvailableKeysError):
        await gateway.proxy_request(
            user_id=test_user.id,
            build_request=_build_request(),
            provider_type=ProviderType.GEMINI,
        )

    events = await publisher.recent(test_user.id, limit=10)
    assert len(events) == 1
    assert events[0].outcome == "no_keys"
    assert events[0].key_id is None


@pytest.mark.asyncio
async def test_events_never_leak_across_users(key_pool, fake_redis, test_user, other_user, _patch_registry):
    await _create_active_key(key_pool, test_user.id, "mine")
    await _create_active_key(key_pool, other_user.id, "theirs")
    publisher = RequestEventPublisher(fake_redis)
    gateway = GatewayService(key_pool, max_attempts=3, event_publisher=publisher)

    _patch_registry(ScriptedProvider([200]))
    await gateway.proxy_request(
        user_id=test_user.id,
        build_request=_build_request(),
        provider_type=ProviderType.GEMINI,
    )
    _patch_registry(ScriptedProvider([200]))
    await gateway.proxy_request(
        user_id=other_user.id,
        build_request=_build_request(),
        provider_type=ProviderType.GEMINI,
    )

    my_events = await publisher.recent(test_user.id, limit=10)
    their_events = await publisher.recent(other_user.id, limit=10)
    assert len(my_events) == 1
    assert len(their_events) == 1
    assert my_events[0].user_id == test_user.id
    assert their_events[0].user_id == other_user.id


@pytest.mark.asyncio
async def test_no_publisher_configured_does_not_raise(key_pool, test_user, _patch_registry):
    await _create_active_key(key_pool, test_user.id, "k1")
    provider = ScriptedProvider([200])
    _patch_registry(provider)
    gateway = GatewayService(key_pool, max_attempts=3)

    response = await gateway.proxy_request(
        user_id=test_user.id,
        build_request=_build_request(),
        provider_type=ProviderType.GEMINI,
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_successful_request_captures_token_usage(key_pool, fake_redis, test_user, _patch_registry):
    await _create_active_key(key_pool, test_user.id, "k1")
    provider = UsageMetadataProvider({"promptTokenCount": 120, "candidatesTokenCount": 45, "totalTokenCount": 165})
    _patch_registry(provider)
    publisher = RequestEventPublisher(fake_redis)
    gateway = GatewayService(key_pool, max_attempts=3, event_publisher=publisher)

    await gateway.proxy_request(
        user_id=test_user.id,
        build_request=_build_request(),
        provider_type=ProviderType.GEMINI,
    )

    events = await publisher.recent(test_user.id, limit=10)
    assert len(events) == 1
    assert events[0].prompt_tokens == 120
    assert events[0].completion_tokens == 45
    assert events[0].total_tokens == 165


@pytest.mark.asyncio
async def test_missing_usage_metadata_does_not_raise(key_pool, fake_redis, test_user, _patch_registry):
    await _create_active_key(key_pool, test_user.id, "k1")
    provider = UsageMetadataProvider(usage_metadata=None)
    _patch_registry(provider)
    publisher = RequestEventPublisher(fake_redis)
    gateway = GatewayService(key_pool, max_attempts=3, event_publisher=publisher)

    response = await gateway.proxy_request(
        user_id=test_user.id,
        build_request=_build_request(),
        provider_type=ProviderType.GEMINI,
    )

    assert response.status_code == 200
    events = await publisher.recent(test_user.id, limit=10)
    assert events[0].prompt_tokens is None
    assert events[0].completion_tokens is None
    assert events[0].total_tokens is None


@pytest.mark.asyncio
async def test_cross_provider_failover_rebuilds_request_per_attempt(key_pool, test_user, monkeypatch):
    from app.keys.schemas import APIKeyCreate, APIKeyDTO

    gem_key = await key_pool.create_key(
        test_user.id,
        APIKeyCreate(label="gem", provider=ProviderType.GEMINI, raw_key="raw-gem", daily_limit=100),
    )
    or_key = await key_pool.create_key(
        test_user.id,
        APIKeyCreate(label="or", provider=ProviderType.OPENROUTER, raw_key="raw-or", daily_limit=100),
    )

    gem_dto = APIKeyDTO(
        id=gem_key.id, user_id=test_user.id, label="gem", provider=ProviderType.GEMINI,
        status=gem_key.status, requests_today=0, daily_limit=100, decrypted_key="raw-gem",
    )
    or_dto = APIKeyDTO(
        id=or_key.id, user_id=test_user.id, label="or", provider=ProviderType.OPENROUTER,
        status=or_key.status, requests_today=0, daily_limit=100, decrypted_key="raw-or",
    )
    select_sequence = iter([gem_dto, or_dto])
    monkeypatch.setattr(key_pool, "select_key", lambda *a, **kw: _async_return(next(select_sequence)))

    gemini_provider = ScriptedProvider([429])
    openrouter_provider = ScriptedProvider([200])

    def fake_get_provider(name: str):
        return {"gemini": gemini_provider, "openrouter": openrouter_provider}[name]

    monkeypatch.setattr("app.gateway.proxy_service.get_provider", fake_get_provider)

    seen_provider_types = []

    def build_request(dto):
        seen_provider_types.append(dto.provider)
        if dto.provider is ProviderType.GEMINI:
            return UpstreamRequestSpec(path="gemini-path", method="POST", payload={"gemini": True}, headers={})
        return UpstreamRequestSpec(path="v1/chat/completions", method="POST", payload={"openrouter": True}, headers={})

    gateway = GatewayService(key_pool, max_attempts=5)
    response = await gateway.proxy_request(
        user_id=test_user.id,
        build_request=build_request,
        provider_type=None,
    )

    assert response.status_code == 200
    assert seen_provider_types == [ProviderType.GEMINI, ProviderType.OPENROUTER]
    assert gemini_provider.calls == ["raw-gem"]
    assert openrouter_provider.calls == ["raw-or"]


async def _async_return(value):
    return value


@pytest.mark.asyncio
async def test_stream_success_emits_no_event_before_tokens_recorded(key_pool, fake_redis, test_user, _patch_registry):
    await _create_active_key(key_pool, test_user.id, "k1")
    provider = ScriptedStreamProvider([200])
    _patch_registry(provider)
    publisher = RequestEventPublisher(fake_redis)
    gateway = GatewayService(key_pool, max_attempts=3, event_publisher=publisher)

    async with gateway.proxy_stream_request(
        user_id=test_user.id,
        build_request=_build_request(),
        provider_type=ProviderType.GEMINI,
    ) as (response, record_tokens):
        assert response.status_code == 200
        events = await publisher.recent(test_user.id, limit=10)
        assert events == []

        await record_tokens(120, 45, 165)

    events = await publisher.recent(test_user.id, limit=10)
    assert len(events) == 1
    assert events[0].outcome == "success"
    assert events[0].prompt_tokens == 120
    assert events[0].completion_tokens == 45
    assert events[0].total_tokens == 165


@pytest.mark.asyncio
async def test_stream_never_records_tokens_if_caller_does_not_call_it(
    key_pool, fake_redis, test_user, _patch_registry
):
    await _create_active_key(key_pool, test_user.id, "k1")
    provider = ScriptedStreamProvider([200])
    _patch_registry(provider)
    publisher = RequestEventPublisher(fake_redis)
    gateway = GatewayService(key_pool, max_attempts=3, event_publisher=publisher)

    async with gateway.proxy_stream_request(
        user_id=test_user.id,
        build_request=_build_request(),
        provider_type=ProviderType.GEMINI,
    ) as (response, _record_tokens):
        assert response.status_code == 200

    events = await publisher.recent(test_user.id, limit=10)
    assert events == []


@pytest.mark.asyncio
async def test_stream_429_triggers_failover_to_second_key(key_pool, test_user, _patch_registry):
    await _create_active_key(key_pool, test_user.id, "k1")
    await _create_active_key(key_pool, test_user.id, "k2")
    provider = ScriptedStreamProvider([429, 200])
    _patch_registry(provider)
    gateway = GatewayService(key_pool, max_attempts=3)

    async with gateway.proxy_stream_request(
        user_id=test_user.id,
        build_request=_build_request(),
        provider_type=ProviderType.GEMINI,
    ) as (response, record_tokens):
        assert response.status_code == 200
        await record_tokens(None, None, None)

    assert len(provider.calls) == 2


@pytest.mark.asyncio
async def test_stream_no_keys_available_raises(key_pool, test_user, _patch_registry):
    provider = ScriptedStreamProvider([])
    _patch_registry(provider)
    gateway = GatewayService(key_pool, max_attempts=3)

    with pytest.raises(NoAvailableKeysError):
        async with gateway.proxy_stream_request(
            user_id=test_user.id,
            build_request=_build_request(),
            provider_type=ProviderType.GEMINI,
        ):
            pass