from datetime import UTC, datetime, timedelta

import pytest

from app.core.exceptions import KeyNotFoundError
from app.keys.enums import KeyStatus, ProviderType


@pytest.mark.asyncio
async def test_create_and_get(key_repo, test_user):
    key = await key_repo.create(
        user_id=test_user.id, label="test-key", provider=ProviderType.GEMINI, key_encrypted="ciphertext", daily_limit=100
    )
    fetched = await key_repo.get(key.id, user_id=test_user.id)
    assert fetched.label == "test-key"
    assert fetched.status == KeyStatus.ACTIVE


@pytest.mark.asyncio
async def test_get_missing_raises(key_repo, test_user):
    with pytest.raises(KeyNotFoundError):
        await key_repo.get(999, user_id=test_user.id)


@pytest.mark.asyncio
async def test_get_other_users_key_raises(key_repo, test_user, other_user):
    key = await key_repo.create(
        user_id=other_user.id, label="not-yours", provider=ProviderType.GEMINI, key_encrypted="c", daily_limit=100
    )
    with pytest.raises(KeyNotFoundError):
        await key_repo.get(key.id, user_id=test_user.id)


@pytest.mark.asyncio
async def test_list_active_filters_by_status_and_provider(key_repo, test_user):
    active = await key_repo.create(
        user_id=test_user.id, label="active", provider=ProviderType.GEMINI, key_encrypted="c1", daily_limit=100
    )
    cooling = await key_repo.create(
        user_id=test_user.id, label="cooling", provider=ProviderType.GEMINI, key_encrypted="c2", daily_limit=100
    )
    await key_repo.mark_status(cooling.id, KeyStatus.COOLDOWN, user_id=test_user.id)

    result = await key_repo.list_active(user_id=test_user.id, provider=ProviderType.GEMINI)

    assert [k.id for k in result] == [active.id]


@pytest.mark.asyncio
async def test_list_active_excludes_other_users_keys(key_repo, test_user, other_user):
    await key_repo.create(
        user_id=other_user.id, label="theirs", provider=ProviderType.GEMINI, key_encrypted="c1", daily_limit=100
    )
    mine = await key_repo.create(
        user_id=test_user.id, label="mine", provider=ProviderType.GEMINI, key_encrypted="c2", daily_limit=100
    )

    result = await key_repo.list_active(user_id=test_user.id, provider=ProviderType.GEMINI)

    assert [k.id for k in result] == [mine.id]


@pytest.mark.asyncio
async def test_increment_usage(key_repo, test_user):
    key = await key_repo.create(
        user_id=test_user.id, label="k", provider=ProviderType.GEMINI, key_encrypted="c", daily_limit=100
    )
    await key_repo.increment_usage(key.id, user_id=test_user.id)
    await key_repo.increment_usage(key.id, user_id=test_user.id)

    fetched = await key_repo.get(key.id, user_id=test_user.id)
    assert fetched.requests_today == 2
    assert fetched.last_used_at is not None


@pytest.mark.asyncio
async def test_reset_daily_counters_revives_cooldown_and_exhausted(key_repo, test_user):
    key = await key_repo.create(
        user_id=test_user.id, label="k", provider=ProviderType.GEMINI, key_encrypted="c", daily_limit=100
    )
    await key_repo.increment_usage(key.id, user_id=test_user.id)
    await key_repo.mark_status(key.id, KeyStatus.EXHAUSTED, user_id=test_user.id)

    affected = await key_repo.reset_daily_counters()

    fetched = await key_repo.get(key.id, user_id=test_user.id)
    assert [k.id for k in affected] == [key.id]
    assert fetched.status == KeyStatus.ACTIVE
    assert fetched.requests_today == 0


@pytest.mark.asyncio
async def test_reset_daily_counters_leaves_disabled_alone(key_repo, test_user):
    key = await key_repo.create(
        user_id=test_user.id, label="k", provider=ProviderType.GEMINI, key_encrypted="c", daily_limit=100
    )
    await key_repo.mark_status(key.id, KeyStatus.DISABLED, user_id=test_user.id)

    await key_repo.reset_daily_counters()

    fetched = await key_repo.get(key.id, user_id=test_user.id)
    assert fetched.status == KeyStatus.DISABLED


@pytest.mark.asyncio
async def test_reset_daily_counters_spans_all_users(key_repo, test_user, other_user):
    mine = await key_repo.create(
        user_id=test_user.id, label="mine", provider=ProviderType.GEMINI, key_encrypted="c1", daily_limit=100
    )
    theirs = await key_repo.create(
        user_id=other_user.id, label="theirs", provider=ProviderType.GEMINI, key_encrypted="c2", daily_limit=100
    )
    await key_repo.increment_usage(mine.id, user_id=test_user.id)
    await key_repo.increment_usage(theirs.id, user_id=other_user.id)

    affected = await key_repo.reset_daily_counters()

    assert {k.id for k in affected} == {mine.id, theirs.id}


@pytest.mark.asyncio
async def test_clear_expired_cooldowns_only_touches_past_deadlines(key_repo, test_user):
    past_key = await key_repo.create(
        user_id=test_user.id, label="past", provider=ProviderType.GEMINI, key_encrypted="c1", daily_limit=100
    )
    future_key = await key_repo.create(
        user_id=test_user.id, label="future", provider=ProviderType.GEMINI, key_encrypted="c2", daily_limit=100
    )
    now = datetime.now(UTC)
    await key_repo.mark_status(
        past_key.id, KeyStatus.COOLDOWN, user_id=test_user.id, cooldown_until=now - timedelta(minutes=1)
    )
    await key_repo.mark_status(
        future_key.id, KeyStatus.COOLDOWN, user_id=test_user.id, cooldown_until=now + timedelta(hours=1)
    )

    affected = await key_repo.clear_expired_cooldowns(now=now)

    assert [k.id for k in affected] == [past_key.id]
    revived = await key_repo.get(past_key.id, user_id=test_user.id)
    still_cooling = await key_repo.get(future_key.id, user_id=test_user.id)
    assert revived.status == KeyStatus.ACTIVE
    assert still_cooling.status == KeyStatus.COOLDOWN
