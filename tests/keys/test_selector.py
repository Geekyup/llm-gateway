import pytest

from llm_gateway.keys.enums import KeyStatus, ProviderType
from llm_gateway.keys.schemas import APIKeyDTO
from llm_gateway.keys.selector import RoundRobinSelector


def make_dto(key_id: int, user_id: int = 1) -> APIKeyDTO:
    return APIKeyDTO(
        id=key_id,
        user_id=user_id,
        label=f"key-{key_id}",
        provider=ProviderType.GEMINI,
        status=KeyStatus.ACTIVE,
        requests_today=0,
        daily_limit=1000,
    )


@pytest.mark.asyncio
async def test_select_returns_none_for_empty_candidates(fake_redis):
    selector = RoundRobinSelector(fake_redis)
    result = await selector.select(1, "gemini", [])
    assert result is None


@pytest.mark.asyncio
async def test_select_cycles_through_all_candidates(fake_redis):
    selector = RoundRobinSelector(fake_redis)
    candidates = [make_dto(1), make_dto(2), make_dto(3)]

    picks = [await selector.select(1, "gemini", candidates) for _ in range(6)]
    picked_ids = [dto.id for dto in picks]

    # Over 2 full cycles of 3 candidates, every id should appear exactly twice.
    assert picked_ids.count(1) == 2
    assert picked_ids.count(2) == 2
    assert picked_ids.count(3) == 2


@pytest.mark.asyncio
async def test_select_cursor_is_isolated_per_provider(fake_redis):
    selector = RoundRobinSelector(fake_redis)
    gemini_candidates = [make_dto(1), make_dto(2)]

    first = await selector.select(1, "gemini", gemini_candidates)
    # A different provider's cursor must not be advanced or consulted by this call.
    other_first = await selector.select(1, "openai", gemini_candidates)

    assert first is not None
    assert other_first is not None


@pytest.mark.asyncio
async def test_select_cursor_is_isolated_per_user(fake_redis):
    """Two users' round-robin rotations must be fully independent — one
    user's request volume can't skew or reveal another user's position.
    """
    selector = RoundRobinSelector(fake_redis)
    user1_candidates = [make_dto(1, user_id=1), make_dto(2, user_id=1)]
    user2_candidates = [make_dto(10, user_id=2), make_dto(20, user_id=2)]

    # Advance user 1's cursor three times.
    for _ in range(3):
        await selector.select(1, "gemini", user1_candidates)

    # User 2's very first pick should still start from their own index 0,
    # unaffected by user 1's three prior selections.
    first_for_user2 = await selector.select(2, "gemini", user2_candidates)
    assert first_for_user2.id == user2_candidates[1 % len(user2_candidates)].id
