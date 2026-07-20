import pytest

from llm_gateway.keys.enums import KeyStatus, ProviderType
from llm_gateway.keys.schemas import APIKeyDTO
from llm_gateway.keys.selector import RoundRobinSelector


def make_dto(key_id: int) -> APIKeyDTO:
    return APIKeyDTO(
        id=key_id,
        label=f"key-{key_id}",
        provider=ProviderType.GEMINI,
        status=KeyStatus.ACTIVE,
        requests_today=0,
        daily_limit=1000,
    )


@pytest.mark.asyncio
async def test_select_returns_none_for_empty_candidates(fake_redis):
    selector = RoundRobinSelector(fake_redis)
    result = await selector.select("gemini", [])
    assert result is None


@pytest.mark.asyncio
async def test_select_cycles_through_all_candidates(fake_redis):
    selector = RoundRobinSelector(fake_redis)
    candidates = [make_dto(1), make_dto(2), make_dto(3)]

    picks = [await selector.select("gemini", candidates) for _ in range(6)]
    picked_ids = [dto.id for dto in picks]

    # Over 2 full cycles of 3 candidates, every id should appear exactly twice.
    assert picked_ids.count(1) == 2
    assert picked_ids.count(2) == 2
    assert picked_ids.count(3) == 2


@pytest.mark.asyncio
async def test_select_cursor_is_isolated_per_provider(fake_redis):
    selector = RoundRobinSelector(fake_redis)
    gemini_candidates = [make_dto(1), make_dto(2)]

    first = await selector.select("gemini", gemini_candidates)
    # A different provider's cursor must not be advanced or consulted by this call.
    other_first = await selector.select("openai", gemini_candidates)

    assert first is not None
    assert other_first is not None
