from unittest.mock import AsyncMock, patch

import pytest

from app.keys.cache import KeyStatusCache
from app.keys.enums import KeyStatus, ProviderType
from app.keys.selector import RoundRobinSelector
from app.keys.service import KeyPoolService
from app.providers.base import HealthCheckResult


@pytest.fixture
def key_pool_service(key_repo, fake_redis):
    cache = KeyStatusCache(fake_redis, ttl_seconds=30)
    selector = RoundRobinSelector(fake_redis)
    return KeyPoolService(key_repo, cache, selector)


@pytest.mark.asyncio
async def test_check_key_health_revives_exhausted_key(key_repo, key_pool_service, test_user):
    key = await key_repo.create(
        user_id=test_user.id, label="k1", provider=ProviderType.GEMINI, key_encrypted="ciphertext", daily_limit=100
    )
    await key_repo.mark_status(key.id, KeyStatus.EXHAUSTED, user_id=test_user.id)

    fake_provider = AsyncMock()
    fake_provider.health_check.return_value = HealthCheckResult(ok=True)

    with patch("app.keys.service.get_provider", return_value=fake_provider), \
         patch("app.keys.service.decrypt_key", return_value="plaintext-key"):
        result = await key_pool_service.check_key_health(key.id, test_user.id)

    assert result.ok is True
    assert result.detail is None
    fake_provider.health_check.assert_awaited_once_with("plaintext-key")

    refreshed = await key_repo.get(key.id, user_id=test_user.id)
    assert refreshed.status == KeyStatus.ACTIVE


@pytest.mark.asyncio
async def test_check_key_health_marks_active_key_exhausted_on_failure(key_repo, key_pool_service, test_user):
    key = await key_repo.create(
        user_id=test_user.id, label="k1", provider=ProviderType.GEMINI, key_encrypted="ciphertext", daily_limit=100
    )

    fake_provider = AsyncMock()
    fake_provider.health_check.return_value = HealthCheckResult(ok=False, detail="HTTP 401: API key not valid")

    with patch("app.keys.service.get_provider", return_value=fake_provider), \
         patch("app.keys.service.decrypt_key", return_value="plaintext-key"):
        result = await key_pool_service.check_key_health(key.id, test_user.id)

    assert result.ok is False
    assert result.detail == "HTTP 401: API key not valid"

    refreshed = await key_repo.get(key.id, user_id=test_user.id)
    assert refreshed.status == KeyStatus.EXHAUSTED


@pytest.mark.asyncio
async def test_check_key_health_never_reactivates_disabled_key(key_repo, key_pool_service, test_user):
    key = await key_repo.create(
        user_id=test_user.id, label="k1", provider=ProviderType.GEMINI, key_encrypted="ciphertext", daily_limit=100
    )
    await key_repo.mark_status(key.id, KeyStatus.DISABLED, user_id=test_user.id)

    fake_provider = AsyncMock()
    fake_provider.health_check.return_value = HealthCheckResult(ok=True)

    with patch("app.keys.service.get_provider", return_value=fake_provider), \
         patch("app.keys.service.decrypt_key", return_value="plaintext-key"):
        result = await key_pool_service.check_key_health(key.id, test_user.id)

    assert result.ok is True
    refreshed = await key_repo.get(key.id, user_id=test_user.id)
    # A manually-disabled key stays disabled even if the upstream key works —
    # health checks should never override an explicit admin decision.
    assert refreshed.status == KeyStatus.DISABLED


@pytest.mark.asyncio
async def test_check_key_health_leaves_cooldown_key_alone_on_failure(key_repo, key_pool_service, test_user):
    key = await key_repo.create(
        user_id=test_user.id, label="k1", provider=ProviderType.GEMINI, key_encrypted="ciphertext", daily_limit=100
    )
    await key_repo.mark_status(key.id, KeyStatus.COOLDOWN, user_id=test_user.id)

    fake_provider = AsyncMock()
    fake_provider.health_check.return_value = HealthCheckResult(ok=False, detail="HTTP 429")

    with patch("app.keys.service.get_provider", return_value=fake_provider), \
         patch("app.keys.service.decrypt_key", return_value="plaintext-key"):
        result = await key_pool_service.check_key_health(key.id, test_user.id)

    assert result.ok is False
    refreshed = await key_repo.get(key.id, user_id=test_user.id)
    # Cooldown already has its own recovery timer — a failed health check
    # shouldn't reclassify it as EXHAUSTED.
    assert refreshed.status == KeyStatus.COOLDOWN


@pytest.mark.asyncio
async def test_check_all_keys_skips_disabled(key_repo, key_pool_service, test_user):
    active = await key_repo.create(
        user_id=test_user.id, label="active", provider=ProviderType.GEMINI, key_encrypted="c1", daily_limit=100
    )
    disabled = await key_repo.create(
        user_id=test_user.id, label="disabled", provider=ProviderType.GEMINI, key_encrypted="c2", daily_limit=100
    )
    await key_repo.mark_status(disabled.id, KeyStatus.DISABLED, user_id=test_user.id)

    fake_provider = AsyncMock()
    fake_provider.health_check.return_value = HealthCheckResult(ok=True)

    with patch("app.keys.service.get_provider", return_value=fake_provider), \
         patch("app.keys.service.decrypt_key", return_value="plaintext-key"):
        results = await key_pool_service.check_all_keys(test_user.id)

    assert [r.key_id for r in results] == [active.id]


@pytest.mark.asyncio
async def test_check_all_keys_never_touches_other_users_keys(key_repo, key_pool_service, test_user, other_user):
    await key_repo.create(
        user_id=other_user.id, label="not-yours", provider=ProviderType.GEMINI, key_encrypted="c1", daily_limit=100
    )
    mine = await key_repo.create(
        user_id=test_user.id, label="mine", provider=ProviderType.GEMINI, key_encrypted="c2", daily_limit=100
    )

    fake_provider = AsyncMock()
    fake_provider.health_check.return_value = HealthCheckResult(ok=True)

    with patch("app.keys.service.get_provider", return_value=fake_provider), \
         patch("app.keys.service.decrypt_key", return_value="plaintext-key"):
        results = await key_pool_service.check_all_keys(test_user.id)

    assert [r.key_id for r in results] == [mine.id]
