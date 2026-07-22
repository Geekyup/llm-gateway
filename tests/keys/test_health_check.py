from unittest.mock import AsyncMock, patch

import pytest

from llm_gateway.keys.cache import KeyStatusCache
from llm_gateway.keys.enums import KeyStatus, ProviderType
from llm_gateway.keys.selector import RoundRobinSelector
from llm_gateway.keys.service import KeyPoolService
from llm_gateway.providers.base import HealthCheckResult


@pytest.fixture
def key_pool_service(key_repo, fake_redis):
    cache = KeyStatusCache(fake_redis, ttl_seconds=30)
    selector = RoundRobinSelector(fake_redis)
    return KeyPoolService(key_repo, cache, selector)


@pytest.mark.asyncio
async def test_check_key_health_revives_exhausted_key(key_repo, key_pool_service):
    key = await key_repo.create(
        label="k1", provider=ProviderType.GEMINI, key_encrypted="ciphertext", daily_limit=100
    )
    await key_repo.mark_status(key.id, KeyStatus.EXHAUSTED)

    fake_provider = AsyncMock()
    fake_provider.health_check.return_value = HealthCheckResult(ok=True)

    with patch("llm_gateway.keys.service.get_provider", return_value=fake_provider), \
         patch("llm_gateway.keys.service.decrypt_key", return_value="plaintext-key"):
        result = await key_pool_service.check_key_health(key.id)

    assert result.ok is True
    assert result.detail is None
    fake_provider.health_check.assert_awaited_once_with("plaintext-key")

    refreshed = await key_repo.get(key.id)
    assert refreshed.status == KeyStatus.ACTIVE


@pytest.mark.asyncio
async def test_check_key_health_marks_active_key_exhausted_on_failure(key_repo, key_pool_service):
    key = await key_repo.create(
        label="k1", provider=ProviderType.GEMINI, key_encrypted="ciphertext", daily_limit=100
    )

    fake_provider = AsyncMock()
    fake_provider.health_check.return_value = HealthCheckResult(ok=False, detail="HTTP 401: API key not valid")

    with patch("llm_gateway.keys.service.get_provider", return_value=fake_provider), \
         patch("llm_gateway.keys.service.decrypt_key", return_value="plaintext-key"):
        result = await key_pool_service.check_key_health(key.id)

    assert result.ok is False
    assert result.detail == "HTTP 401: API key not valid"

    refreshed = await key_repo.get(key.id)
    assert refreshed.status == KeyStatus.EXHAUSTED


@pytest.mark.asyncio
async def test_check_key_health_never_reactivates_disabled_key(key_repo, key_pool_service):
    key = await key_repo.create(
        label="k1", provider=ProviderType.GEMINI, key_encrypted="ciphertext", daily_limit=100
    )
    await key_repo.mark_status(key.id, KeyStatus.DISABLED)

    fake_provider = AsyncMock()
    fake_provider.health_check.return_value = HealthCheckResult(ok=True)

    with patch("llm_gateway.keys.service.get_provider", return_value=fake_provider), \
         patch("llm_gateway.keys.service.decrypt_key", return_value="plaintext-key"):
        result = await key_pool_service.check_key_health(key.id)

    assert result.ok is True
    refreshed = await key_repo.get(key.id)
    # A manually-disabled key stays disabled even if the upstream key works —
    # health checks should never override an explicit admin decision.
    assert refreshed.status == KeyStatus.DISABLED


@pytest.mark.asyncio
async def test_check_key_health_leaves_cooldown_key_alone_on_failure(key_repo, key_pool_service):
    key = await key_repo.create(
        label="k1", provider=ProviderType.GEMINI, key_encrypted="ciphertext", daily_limit=100
    )
    await key_repo.mark_status(key.id, KeyStatus.COOLDOWN)

    fake_provider = AsyncMock()
    fake_provider.health_check.return_value = HealthCheckResult(ok=False, detail="HTTP 429")

    with patch("llm_gateway.keys.service.get_provider", return_value=fake_provider), \
         patch("llm_gateway.keys.service.decrypt_key", return_value="plaintext-key"):
        result = await key_pool_service.check_key_health(key.id)

    assert result.ok is False
    refreshed = await key_repo.get(key.id)
    # Cooldown already has its own recovery timer — a failed health check
    # shouldn't reclassify it as EXHAUSTED.
    assert refreshed.status == KeyStatus.COOLDOWN


@pytest.mark.asyncio
async def test_check_all_keys_skips_disabled(key_repo, key_pool_service):
    active = await key_repo.create(
        label="active", provider=ProviderType.GEMINI, key_encrypted="c1", daily_limit=100
    )
    disabled = await key_repo.create(
        label="disabled", provider=ProviderType.GEMINI, key_encrypted="c2", daily_limit=100
    )
    await key_repo.mark_status(disabled.id, KeyStatus.DISABLED)

    fake_provider = AsyncMock()
    fake_provider.health_check.return_value = HealthCheckResult(ok=True)

    with patch("llm_gateway.keys.service.get_provider", return_value=fake_provider), \
         patch("llm_gateway.keys.service.decrypt_key", return_value="plaintext-key"):
        results = await key_pool_service.check_all_keys()

    assert [r.key_id for r in results] == [active.id]
