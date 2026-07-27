"""Tests for KeyPoolService's model-pinning behaviour: a key can be
configured to serve one specific upstream model, and a request that asks
for a model should only draw from keys pinned to that exact model.
"""
import pytest

from app.keys.cache import KeyStatusCache
from app.keys.enums import KeyStatus, ProviderType
from app.keys.schemas import APIKeyCreate
from app.keys.selector import RoundRobinSelector
from app.keys.service import KeyPoolService


@pytest.fixture
def key_pool(key_repo, fake_redis):
    cache = KeyStatusCache(fake_redis, ttl_seconds=30)
    selector = RoundRobinSelector(fake_redis)
    return KeyPoolService(key_repo, cache, selector)


async def _create_key(key_pool: KeyPoolService, user_id: int, label: str, model: str | None = None):
    return await key_pool.create_key(
        user_id,
        APIKeyCreate(label=label, provider=ProviderType.GEMINI, raw_key=f"raw-{label}", daily_limit=100, model=model),
    )


@pytest.mark.asyncio
async def test_candidates_for_a_model_only_include_keys_pinned_to_it(key_pool, test_user):
    flash = await _create_key(key_pool, test_user.id, "flash-key", model="gemini-3.6-flash")
    pro = await _create_key(key_pool, test_user.id, "pro-key", model="gemini-3.6-pro")
    await _create_key(key_pool, test_user.id, "other-user-model", model="gemini-3.6-flash")  # different label, same model — control

    candidates = await key_pool.get_candidate_keys(test_user.id, ProviderType.GEMINI, model="gemini-3.6-flash")

    ids = {c.id for c in candidates}
    assert flash.id in ids
    assert pro.id not in ids


@pytest.mark.asyncio
async def test_unpinned_keys_never_match_a_model_specific_request(key_pool, test_user):
    """A key with no model set (model=None) is not a wildcard — it must
    not be silently used for a request that specifies a model, since the
    admin never configured it for that model.
    """
    await _create_key(key_pool, test_user.id, "unpinned", model=None)

    candidates = await key_pool.get_candidate_keys(test_user.id, ProviderType.GEMINI, model="gemini-3.6-flash")

    assert candidates == []


@pytest.mark.asyncio
async def test_model_specific_keys_never_match_a_request_with_no_model(key_pool, test_user):
    """Symmetric to the above: a key pinned to a specific model should not
    be picked up for a request that didn't ask for that model.
    """
    await _create_key(key_pool, test_user.id, "pinned", model="gemini-3.6-flash")

    candidates = await key_pool.get_candidate_keys(test_user.id, ProviderType.GEMINI, model=None)

    assert candidates == []


@pytest.mark.asyncio
async def test_no_model_filter_matches_only_unpinned_keys(key_pool, test_user):
    unpinned = await _create_key(key_pool, test_user.id, "unpinned", model=None)
    await _create_key(key_pool, test_user.id, "pinned", model="gemini-3.6-flash")

    candidates = await key_pool.get_candidate_keys(test_user.id, ProviderType.GEMINI, model=None)

    assert [c.id for c in candidates] == [unpinned.id]


@pytest.mark.asyncio
async def test_select_key_returns_none_when_no_key_matches_requested_model(key_pool, test_user):
    await _create_key(key_pool, test_user.id, "flash-only", model="gemini-3.6-flash")

    chosen = await key_pool.select_key(test_user.id, ProviderType.GEMINI, model="gemini-3.6-pro")

    assert chosen is None


@pytest.mark.asyncio
async def test_select_key_round_robins_within_the_matching_subset_only(key_pool, test_user):
    flash_a = await _create_key(key_pool, test_user.id, "flash-a", model="gemini-3.6-flash")
    flash_b = await _create_key(key_pool, test_user.id, "flash-b", model="gemini-3.6-flash")
    await _create_key(key_pool, test_user.id, "pro-only", model="gemini-3.6-pro")

    picks = set()
    for _ in range(4):
        chosen = await key_pool.select_key(test_user.id, ProviderType.GEMINI, model="gemini-3.6-flash")
        picks.add(chosen.id)

    # Only the two flash-pinned keys should ever be picked — the pro-only
    # key must never appear no matter how many times we rotate.
    assert picks == {flash_a.id, flash_b.id}


@pytest.mark.asyncio
async def test_cache_hit_still_gets_filtered_by_model(key_pool, test_user, fake_redis):
    """The active-key cache stores the full per-(user, provider) list — the
    model filter must still apply on a cache hit, not just on a cold read
    from Postgres.
    """
    flash = await _create_key(key_pool, test_user.id, "flash", model="gemini-3.6-flash")
    await _create_key(key_pool, test_user.id, "pro", model="gemini-3.6-pro")

    # Warm the cache with a call that returns everything unfiltered isn't
    # possible through the public API anymore (model filtering always
    # applies) — instead, call twice with the same model to force a cache
    # hit on the second call and confirm filtering still holds.
    first = await key_pool.get_candidate_keys(test_user.id, ProviderType.GEMINI, model="gemini-3.6-flash")
    second = await key_pool.get_candidate_keys(test_user.id, ProviderType.GEMINI, model="gemini-3.6-flash")

    assert [c.id for c in first] == [flash.id]
    assert [c.id for c in second] == [flash.id]


@pytest.mark.asyncio
async def test_disabled_key_pinned_to_model_is_never_a_candidate(key_pool, test_user):
    key = await _create_key(key_pool, test_user.id, "flash", model="gemini-3.6-flash")
    await key_pool.set_status(key.id, test_user.id, KeyStatus.DISABLED)

    candidates = await key_pool.get_candidate_keys(test_user.id, ProviderType.GEMINI, model="gemini-3.6-flash")

    assert candidates == []
