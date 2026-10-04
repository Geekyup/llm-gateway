import pytest

from app.core.exceptions import DuplicateKeyError
from app.keys.cache import KeyStatusCache
from app.keys.enums import KeyStatus, ProviderType
from app.keys.schemas import APIKeyBulkCreate, APIKeyCreate
from app.keys.selector import RoundRobinSelector
from app.keys.service import KeyPoolService


@pytest.fixture
def key_pool(key_repo, fake_redis):
    cache = KeyStatusCache(fake_redis, ttl_seconds=30)
    selector = RoundRobinSelector(fake_redis)
    return KeyPoolService(key_repo, cache, selector)


def _cache_key(key_pool: KeyPoolService, user_id: int) -> str:
    return key_pool._cache._cache_key(user_id, ProviderType.GEMINI.value)


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
async def test_unpinned_keys_match_any_model_specific_request(key_pool, test_user):
    unpinned = await _create_key(key_pool, test_user.id, "unpinned", model=None)

    candidates = await key_pool.get_candidate_keys(test_user.id, ProviderType.GEMINI, model="gemini-3.6-flash")

    assert [c.id for c in candidates] == [unpinned.id]


@pytest.mark.asyncio
async def test_a_request_with_no_model_matches_any_key(key_pool, test_user):
    pinned = await _create_key(key_pool, test_user.id, "pinned", model="gemini-3.6-flash")

    candidates = await key_pool.get_candidate_keys(test_user.id, ProviderType.GEMINI, model=None)

    assert [c.id for c in candidates] == [pinned.id]


@pytest.mark.asyncio
async def test_no_model_filter_matches_every_active_key(key_pool, test_user):
    unpinned = await _create_key(key_pool, test_user.id, "unpinned", model=None)
    pinned = await _create_key(key_pool, test_user.id, "pinned", model="gemini-3.6-flash")

    candidates = await key_pool.get_candidate_keys(test_user.id, ProviderType.GEMINI, model=None)

    assert {c.id for c in candidates} == {unpinned.id, pinned.id}


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

    assert picks == {flash_a.id, flash_b.id}


@pytest.mark.asyncio
async def test_cache_hit_still_gets_filtered_by_model(key_pool, test_user, fake_redis):
    flash = await _create_key(key_pool, test_user.id, "flash", model="gemini-3.6-flash")
    await _create_key(key_pool, test_user.id, "pro", model="gemini-3.6-pro")

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

@pytest.mark.asyncio
async def test_cache_never_holds_plaintext_key(key_pool, test_user, fake_redis):
    key = await _create_key(key_pool, test_user.id, "secret-holder")

    await key_pool.get_candidate_keys(test_user.id, ProviderType.GEMINI)

    raw = await fake_redis.get(_cache_key(key_pool, test_user.id))
    assert raw is not None
    assert "raw-secret-holder" not in raw
    assert "decrypted_key" not in raw
    assert key.key_encrypted in raw


@pytest.mark.asyncio
async def test_selected_candidate_decrypts_to_the_original_key(key_pool, test_user):
    await _create_key(key_pool, test_user.id, "k1")

    chosen = await key_pool.select_key(test_user.id, ProviderType.GEMINI)

    assert chosen is not None
    assert chosen.decrypted_key == "raw-k1"


@pytest.mark.asyncio
async def test_exclude_ids_filters_cached_candidates(key_pool, test_user):
    first = await _create_key(key_pool, test_user.id, "k1")
    second = await _create_key(key_pool, test_user.id, "k2")

    await key_pool.get_candidate_keys(test_user.id, ProviderType.GEMINI)
    candidates = await key_pool.get_candidate_keys(
        test_user.id, ProviderType.GEMINI, exclude_ids={first.id}
    )

    assert [c.id for c in candidates] == [second.id]


@pytest.mark.asyncio
async def test_record_success_keeps_cache_while_under_limit(key_pool, test_user, fake_redis):
    key = await _create_key(key_pool, test_user.id, "k1")
    await key_pool.get_candidate_keys(test_user.id, ProviderType.GEMINI)
    assert await fake_redis.get(_cache_key(key_pool, test_user.id)) is not None

    recorded = await key_pool.record_success(key.id, test_user.id, ProviderType.GEMINI)

    assert recorded is True
    assert await fake_redis.get(_cache_key(key_pool, test_user.id)) is not None


@pytest.mark.asyncio
async def test_record_success_at_daily_limit_exhausts_key_and_invalidates_cache(key_pool, test_user, fake_redis):
    key = await key_pool.create_key(
        test_user.id,
        APIKeyCreate(label="tiny", provider=ProviderType.GEMINI, raw_key="raw-tiny", daily_limit=2),
    )
    await key_pool.get_candidate_keys(test_user.id, ProviderType.GEMINI)

    await key_pool.record_success(key.id, test_user.id, ProviderType.GEMINI)
    assert await fake_redis.get(_cache_key(key_pool, test_user.id)) is not None
    await key_pool.record_success(key.id, test_user.id, ProviderType.GEMINI)

    assert await fake_redis.get(_cache_key(key_pool, test_user.id)) is None
    refreshed = await key_pool.get_key(key.id, test_user.id)
    assert refreshed.status == KeyStatus.EXHAUSTED
    assert refreshed.requests_today == 2
    assert await key_pool.select_key(test_user.id, ProviderType.GEMINI) is None


@pytest.mark.asyncio
async def test_record_success_beyond_limit_returns_false_and_invalidates_cache(key_pool, test_user, fake_redis):
    key = await key_pool.create_key(
        test_user.id,
        APIKeyCreate(label="tiny", provider=ProviderType.GEMINI, raw_key="raw-tiny", daily_limit=1),
    )
    await key_pool.record_success(key.id, test_user.id, ProviderType.GEMINI)
    await key_pool.get_candidate_keys(test_user.id, ProviderType.GEMINI)

    recorded = await key_pool.record_success(key.id, test_user.id, ProviderType.GEMINI)

    assert recorded is False
    assert await fake_redis.get(_cache_key(key_pool, test_user.id)) is None


@pytest.mark.asyncio
async def test_key_at_daily_limit_is_never_a_candidate(key_pool, key_repo, test_user):
    key = await _create_key(key_pool, test_user.id, "full")
    await key_repo.update_fields(key.id, user_id=test_user.id, daily_limit=1, requests_today=1)

    candidates = await key_pool.get_candidate_keys(test_user.id, ProviderType.GEMINI)

    assert candidates == []


@pytest.mark.asyncio
async def test_create_key_rejects_duplicate_raw_key_for_same_provider(key_pool, test_user):
    await _create_key(key_pool, test_user.id, "k1")

    with pytest.raises(DuplicateKeyError):
        await key_pool.create_key(
            test_user.id,
            APIKeyCreate(label="again", provider=ProviderType.GEMINI, raw_key="raw-k1", daily_limit=100),
        )


@pytest.mark.asyncio
async def test_same_raw_key_is_allowed_for_another_provider_and_user(key_pool, test_user, other_user):
    await _create_key(key_pool, test_user.id, "k1")

    await key_pool.create_key(
        test_user.id,
        APIKeyCreate(label="grp", provider=ProviderType.GROQ, raw_key="raw-k1", daily_limit=100),
    )
    await key_pool.create_key(
        other_user.id,
        APIKeyCreate(label="theirs", provider=ProviderType.GEMINI, raw_key="raw-k1", daily_limit=100),
    )


@pytest.mark.asyncio
async def test_bulk_create_skips_duplicates_in_batch_and_existing(key_pool, test_user):
    await _create_key(key_pool, test_user.id, "existing")

    result = await key_pool.create_keys_bulk(
        test_user.id,
        APIKeyBulkCreate(
            provider=ProviderType.GEMINI,
            raw_keys="raw-existing, new-a\nnew-b new-a",
            label_prefix="Bulk",
            daily_limit=50,
        ),
    )

    assert [k.label for k in result.created] == ["Bulk 2", "Bulk 3"]
    assert result.skipped_duplicates == 2
    assert result.errors == []


@pytest.mark.asyncio
async def test_bulk_create_commits_once(key_pool, key_repo, db_session, test_user):
    from sqlalchemy import event

    commits = []
    event.listen(db_session.sync_session, "after_commit", lambda session: commits.append(1))

    await key_pool.create_keys_bulk(
        test_user.id,
        APIKeyBulkCreate(
            provider=ProviderType.GEMINI, raw_keys="k1 k2 k3 k4", label_prefix="B", daily_limit=10
        ),
    )

    assert len(commits) == 1


@pytest.mark.asyncio
async def test_bulk_create_falls_back_when_a_concurrent_insert_wins_the_race(
    key_pool, key_repo, test_user, monkeypatch
):
    from sqlalchemy.exc import IntegrityError

    async def losing_create_many(items):
        await key_repo.create(**items[0])
        raise IntegrityError("insert", {}, Exception("duplicate"))

    monkeypatch.setattr(key_repo, "create_many", losing_create_many)

    result = await key_pool.create_keys_bulk(
        test_user.id,
        APIKeyBulkCreate(
            provider=ProviderType.GEMINI, raw_keys="k1 k2", label_prefix="B", daily_limit=10
        ),
    )

    assert len(result.created) == 1
    assert result.skipped_duplicates == 1
    assert result.errors == []


@pytest.mark.asyncio
async def test_candidates_without_provider_span_all_providers(key_pool, test_user):
    gemini = await _create_key(key_pool, test_user.id, "gem")
    groq = await key_pool.create_key(
        test_user.id,
        APIKeyCreate(label="grq", provider=ProviderType.GROQ, raw_key="raw-grq", daily_limit=100),
    )

    candidates = await key_pool.get_candidate_keys(test_user.id, None)

    assert {c.id for c in candidates} == {gemini.id, groq.id}


@pytest.mark.asyncio
async def test_select_key_without_provider_round_robins_across_providers(key_pool, test_user):
    await _create_key(key_pool, test_user.id, "gem")
    await key_pool.create_key(
        test_user.id,
        APIKeyCreate(label="grq", provider=ProviderType.GROQ, raw_key="raw-grq", daily_limit=100),
    )

    picked = {(await key_pool.select_key(test_user.id, None)).provider for _ in range(4)}

    assert picked == {ProviderType.GEMINI, ProviderType.GROQ}
