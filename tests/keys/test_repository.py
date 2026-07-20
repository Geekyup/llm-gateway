from datetime import datetime, timedelta, timezone

import pytest

from llm_gateway.core.exceptions import KeyNotFoundError
from llm_gateway.keys.enums import KeyStatus, ProviderType


@pytest.mark.asyncio
async def test_create_and_get(key_repo):
    key = await key_repo.create(
        label="test-key", provider=ProviderType.GEMINI, key_encrypted="ciphertext", daily_limit=100
    )
    fetched = await key_repo.get(key.id)
    assert fetched.label == "test-key"
    assert fetched.status == KeyStatus.ACTIVE


@pytest.mark.asyncio
async def test_get_missing_raises(key_repo):
    with pytest.raises(KeyNotFoundError):
        await key_repo.get(999)


@pytest.mark.asyncio
async def test_list_active_filters_by_status_and_provider(key_repo):
    active = await key_repo.create(
        label="active", provider=ProviderType.GEMINI, key_encrypted="c1", daily_limit=100
    )
    cooling = await key_repo.create(
        label="cooling", provider=ProviderType.GEMINI, key_encrypted="c2", daily_limit=100
    )
    await key_repo.mark_status(cooling.id, KeyStatus.COOLDOWN)

    result = await key_repo.list_active(provider=ProviderType.GEMINI)

    assert [k.id for k in result] == [active.id]


@pytest.mark.asyncio
async def test_increment_usage(key_repo):
    key = await key_repo.create(
        label="k", provider=ProviderType.GEMINI, key_encrypted="c", daily_limit=100
    )
    await key_repo.increment_usage(key.id)
    await key_repo.increment_usage(key.id)

    fetched = await key_repo.get(key.id)
    assert fetched.requests_today == 2
    assert fetched.last_used_at is not None


@pytest.mark.asyncio
async def test_reset_daily_counters_revives_cooldown_and_exhausted(key_repo):
    key = await key_repo.create(
        label="k", provider=ProviderType.GEMINI, key_encrypted="c", daily_limit=100
    )
    await key_repo.increment_usage(key.id)
    await key_repo.mark_status(key.id, KeyStatus.EXHAUSTED)

    affected = await key_repo.reset_daily_counters()

    fetched = await key_repo.get(key.id)
    assert affected == 1
    assert fetched.status == KeyStatus.ACTIVE
    assert fetched.requests_today == 0


@pytest.mark.asyncio
async def test_reset_daily_counters_leaves_disabled_alone(key_repo):
    key = await key_repo.create(
        label="k", provider=ProviderType.GEMINI, key_encrypted="c", daily_limit=100
    )
    await key_repo.mark_status(key.id, KeyStatus.DISABLED)

    await key_repo.reset_daily_counters()

    fetched = await key_repo.get(key.id)
    assert fetched.status == KeyStatus.DISABLED


@pytest.mark.asyncio
async def test_clear_expired_cooldowns_only_touches_past_deadlines(key_repo):
    past_key = await key_repo.create(
        label="past", provider=ProviderType.GEMINI, key_encrypted="c1", daily_limit=100
    )
    future_key = await key_repo.create(
        label="future", provider=ProviderType.GEMINI, key_encrypted="c2", daily_limit=100
    )
    now = datetime.now(timezone.utc)
    await key_repo.mark_status(past_key.id, KeyStatus.COOLDOWN, cooldown_until=now - timedelta(minutes=1))
    await key_repo.mark_status(future_key.id, KeyStatus.COOLDOWN, cooldown_until=now + timedelta(hours=1))

    affected = await key_repo.clear_expired_cooldowns(now=now)

    assert affected == 1
    revived = await key_repo.get(past_key.id)
    still_cooling = await key_repo.get(future_key.id)
    assert revived.status == KeyStatus.ACTIVE
    assert still_cooling.status == KeyStatus.COOLDOWN
