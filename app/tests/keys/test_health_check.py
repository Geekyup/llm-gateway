import asyncio
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


@pytest.mark.asyncio
async def test_check_keys_revives_exhausted_and_reports_per_key_results(
    key_repo, key_pool_service, test_user, other_user
):
    mine = await key_repo.create(
        user_id=test_user.id,
        label="m",
        provider=ProviderType.GEMINI,
        key_encrypted="c1",
        daily_limit=100,
    )
    theirs = await key_repo.create(
        user_id=other_user.id,
        label="t",
        provider=ProviderType.GEMINI,
        key_encrypted="c2",
        daily_limit=100,
    )
    await key_repo.mark_status(mine.id, KeyStatus.EXHAUSTED, user_id=test_user.id)
    await key_repo.mark_status(theirs.id, KeyStatus.EXHAUSTED, user_id=other_user.id)

    fake_provider = AsyncMock()
    fake_provider.health_check.return_value = HealthCheckResult(ok=True)
    keys = await key_pool_service.list_all_keys_system_wide(status=KeyStatus.EXHAUSTED)

    with (
        patch("app.keys.service.get_provider", return_value=fake_provider),
        patch("app.keys.service.decrypt_key", return_value="plaintext-key"),
    ):
        results = await key_pool_service.check_keys(keys)

    assert sorted(r.key_id for r in results) == sorted([mine.id, theirs.id])
    assert all(r.ok for r in results)
    assert (await key_repo.get(mine.id, user_id=test_user.id)).status == KeyStatus.ACTIVE
    assert (await key_repo.get(theirs.id, user_id=other_user.id)).status == KeyStatus.ACTIVE


@pytest.mark.asyncio
async def test_check_keys_keeps_failing_key_exhausted(key_repo, key_pool_service, test_user):
    key = await key_repo.create(
        user_id=test_user.id,
        label="k",
        provider=ProviderType.GEMINI,
        key_encrypted="c1",
        daily_limit=100,
    )
    await key_repo.mark_status(key.id, KeyStatus.EXHAUSTED, user_id=test_user.id)

    fake_provider = AsyncMock()
    fake_provider.health_check.return_value = HealthCheckResult(ok=False, detail="HTTP 429")
    keys = await key_pool_service.list_all_keys_system_wide(status=KeyStatus.EXHAUSTED)

    with (
        patch("app.keys.service.get_provider", return_value=fake_provider),
        patch("app.keys.service.decrypt_key", return_value="plaintext-key"),
    ):
        results = await key_pool_service.check_keys(keys)

    assert [(r.key_id, r.ok, r.detail) for r in results] == [(key.id, False, "HTTP 429")]
    assert (await key_repo.get(key.id, user_id=test_user.id)).status == KeyStatus.EXHAUSTED


@pytest.mark.asyncio
async def test_check_keys_with_empty_list_makes_no_requests(key_pool_service):
    fake_provider = AsyncMock()

    with patch("app.keys.service.get_provider", return_value=fake_provider):
        results = await key_pool_service.check_keys([])

    assert results == []
    fake_provider.health_check.assert_not_awaited()


@pytest.mark.asyncio
async def test_check_keys_limits_concurrency_per_provider(key_repo, key_pool_service, test_user):
    keys = []
    for i in range(6):
        key = await key_repo.create(
            user_id=test_user.id,
            label=f"k{i}",
            provider=ProviderType.GEMINI,
            key_encrypted=f"c{i}",
            daily_limit=100,
        )
        await key_repo.mark_status(key.id, KeyStatus.EXHAUSTED, user_id=test_user.id)
        keys.append(key)

    in_flight = 0
    peak = 0

    async def slow_health_check(_key: str) -> HealthCheckResult:
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.01)
        in_flight -= 1
        return HealthCheckResult(ok=True)

    fake_provider = AsyncMock()
    fake_provider.health_check.side_effect = slow_health_check
    exhausted = await key_pool_service.list_all_keys_system_wide(status=KeyStatus.EXHAUSTED)

    with (
        patch("app.keys.service.get_provider", return_value=fake_provider),
        patch("app.keys.service.decrypt_key", return_value="plaintext-key"),
    ):
        results = await key_pool_service.check_keys(exhausted, concurrency=2)

    assert len(results) == 6
    assert peak == 2


@pytest.mark.asyncio
async def test_check_keys_runs_different_providers_in_parallel(
    key_repo, key_pool_service, test_user
):
    for provider in (ProviderType.GEMINI, ProviderType.GROQ, ProviderType.OPENROUTER):
        key = await key_repo.create(
            user_id=test_user.id,
            label=provider.value,
            provider=provider,
            key_encrypted="c",
            daily_limit=100,
        )
        await key_repo.mark_status(key.id, KeyStatus.EXHAUSTED, user_id=test_user.id)

    in_flight = 0
    peak = 0

    async def slow_health_check(_key: str) -> HealthCheckResult:
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.01)
        in_flight -= 1
        return HealthCheckResult(ok=True)

    fake_provider = AsyncMock()
    fake_provider.health_check.side_effect = slow_health_check
    exhausted = await key_pool_service.list_all_keys_system_wide(status=KeyStatus.EXHAUSTED)

    with (
        patch("app.keys.service.get_provider", return_value=fake_provider),
        patch("app.keys.service.decrypt_key", return_value="plaintext-key"),
    ):
        await key_pool_service.check_keys(exhausted, concurrency=1)

    assert peak == 3


@pytest.mark.asyncio
async def test_check_keys_applies_delay_between_requests(key_repo, key_pool_service, test_user):
    for i in range(3):
        key = await key_repo.create(
            user_id=test_user.id,
            label=f"k{i}",
            provider=ProviderType.GEMINI,
            key_encrypted=f"c{i}",
            daily_limit=100,
        )
        await key_repo.mark_status(key.id, KeyStatus.EXHAUSTED, user_id=test_user.id)

    fake_provider = AsyncMock()
    fake_provider.health_check.return_value = HealthCheckResult(ok=True)
    exhausted = await key_pool_service.list_all_keys_system_wide(status=KeyStatus.EXHAUSTED)

    with (
        patch("app.keys.service.get_provider", return_value=fake_provider),
        patch("app.keys.service.decrypt_key", return_value="plaintext-key"),
        patch("app.keys.service.asyncio.sleep", new_callable=AsyncMock) as sleep,
    ):
        await key_pool_service.check_keys(exhausted, concurrency=1, delay_seconds=0.5)

    assert sleep.await_count == 3
    sleep.assert_awaited_with(0.5)


@pytest.mark.asyncio
async def test_check_keys_never_reactivates_disabled_key(key_repo, key_pool_service, test_user):
    key = await key_repo.create(
        user_id=test_user.id,
        label="k",
        provider=ProviderType.GEMINI,
        key_encrypted="c1",
        daily_limit=100,
    )
    await key_repo.mark_status(key.id, KeyStatus.DISABLED, user_id=test_user.id)

    fake_provider = AsyncMock()
    fake_provider.health_check.return_value = HealthCheckResult(ok=True)
    keys = await key_pool_service.list_all_keys_system_wide()

    with (
        patch("app.keys.service.get_provider", return_value=fake_provider),
        patch("app.keys.service.decrypt_key", return_value="plaintext-key"),
    ):
        await key_pool_service.check_keys(keys)

    assert (await key_repo.get(key.id, user_id=test_user.id)).status == KeyStatus.DISABLED


async def _exhausted_key(key_repo, user, label, provider=ProviderType.GEMINI, ciphertext="c"):
    key = await key_repo.create(
        user_id=user.id,
        label=label,
        provider=provider,
        key_encrypted=ciphertext,
        daily_limit=100,
    )
    await key_repo.mark_status(key.id, KeyStatus.EXHAUSTED, user_id=user.id)
    return key


@pytest.mark.asyncio
async def test_check_keys_returns_results_in_input_order(key_repo, key_pool_service, test_user):
    delays = {"slow": 0.03, "mid": 0.02, "fast": 0.01}
    providers = {
        "slow": ProviderType.GEMINI,
        "mid": ProviderType.GROQ,
        "fast": ProviderType.OPENROUTER,
    }
    keys = [
        await _exhausted_key(key_repo, test_user, name, providers[name], ciphertext=name)
        for name in delays
    ]

    async def health_check(plaintext: str) -> HealthCheckResult:
        await asyncio.sleep(delays[plaintext])
        return HealthCheckResult(ok=True)

    fake_provider = AsyncMock()
    fake_provider.health_check.side_effect = health_check

    with (
        patch("app.keys.service.get_provider", return_value=fake_provider),
        patch("app.keys.service.decrypt_key", side_effect=lambda value: value),
    ):
        results = await key_pool_service.check_keys(keys)

    assert [r.key_id for r in results] == [k.id for k in keys]


@pytest.mark.asyncio
async def test_check_all_keys_keeps_key_order_across_providers(
    key_repo, key_pool_service, test_user
):
    keys = [
        await key_repo.create(
            user_id=test_user.id,
            label=f"k{i}",
            provider=provider,
            key_encrypted="c",
            daily_limit=100,
        )
        for i, provider in enumerate(
            [ProviderType.GEMINI, ProviderType.GROQ, ProviderType.GEMINI, ProviderType.GROQ]
        )
    ]
    fake_provider = AsyncMock()
    fake_provider.health_check.return_value = HealthCheckResult(ok=True)

    with (
        patch("app.keys.service.get_provider", return_value=fake_provider),
        patch("app.keys.service.decrypt_key", return_value="plaintext-key"),
    ):
        results = await key_pool_service.check_all_keys(test_user.id)

    assert [r.key_id for r in results] == [k.id for k in keys]


@pytest.mark.asyncio
async def test_check_keys_isolates_a_key_that_cannot_be_probed(
    key_repo, key_pool_service, test_user
):
    good = await _exhausted_key(key_repo, test_user, "good", ciphertext="good")
    broken = await _exhausted_key(key_repo, test_user, "broken", ciphertext="broken")

    def decrypt(value: str) -> str:
        if value == "broken":
            raise ValueError("cannot decrypt")
        return value

    fake_provider = AsyncMock()
    fake_provider.health_check.return_value = HealthCheckResult(ok=True)

    with (
        patch("app.keys.service.get_provider", return_value=fake_provider),
        patch("app.keys.service.decrypt_key", side_effect=decrypt),
    ):
        results = await key_pool_service.check_keys([broken, good])

    by_id = {r.key_id: r for r in results}
    assert by_id[good.id].ok is True
    assert by_id[broken.id].ok is False
    assert by_id[broken.id].detail == "Health check could not be performed"
    assert (await key_repo.get(good.id, user_id=test_user.id)).status == KeyStatus.ACTIVE
    assert (await key_repo.get(broken.id, user_id=test_user.id)).status == KeyStatus.EXHAUSTED


@pytest.mark.asyncio
async def test_check_keys_keeps_applied_results_when_run_is_cancelled(
    key_repo, key_pool_service, test_user
):
    finished = await _exhausted_key(key_repo, test_user, "finished", ciphertext="finished")
    stuck = await _exhausted_key(key_repo, test_user, "stuck", ciphertext="stuck")

    async def health_check(plaintext: str) -> HealthCheckResult:
        if plaintext == "stuck":
            await asyncio.Event().wait()
        return HealthCheckResult(ok=True)

    fake_provider = AsyncMock()
    fake_provider.health_check.side_effect = health_check

    with (
        patch("app.keys.service.get_provider", return_value=fake_provider),
        patch("app.keys.service.decrypt_key", side_effect=lambda value: value),
        pytest.raises(TimeoutError),
    ):
        await asyncio.wait_for(key_pool_service.check_keys([finished, stuck], concurrency=2), 0.2)

    assert (await key_repo.get(finished.id, user_id=test_user.id)).status == KeyStatus.ACTIVE
    assert (await key_repo.get(stuck.id, user_id=test_user.id)).status == KeyStatus.EXHAUSTED
