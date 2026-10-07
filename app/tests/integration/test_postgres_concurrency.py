import asyncio

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.exceptions import DuplicateKeyError
from app.keys.cache import KeyStatusCache
from app.keys.enums import KeyStatus, ProviderType
from app.keys.repository import APIKeyRepository
from app.keys.schemas import APIKeyBulkCreate
from app.keys.selector import RoundRobinSelector
from app.keys.service import KeyPoolService

pytestmark = pytest.mark.integration


async def _create_key(factory, user_id: int, daily_limit: int, key_hash: str | None = None):
    async with factory() as session:
        return await APIKeyRepository(session).create(
            user_id=user_id,
            label="k",
            provider=ProviderType.GEMINI,
            key_encrypted="ciphertext",
            daily_limit=daily_limit,
            key_hash=key_hash,
        )


async def test_concurrent_increments_never_exceed_daily_limit(db_engine, test_user):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    key = await _create_key(factory, test_user.id, daily_limit=10)

    async def attempt():
        async with factory() as session:
            return await APIKeyRepository(session).increment_usage(key.id, user_id=test_user.id)

    results = await asyncio.gather(*(attempt() for _ in range(50)))

    assert sum(result is not None for result in results) == 10
    async with factory() as session:
        stored = await APIKeyRepository(session).get(key.id, user_id=test_user.id)
    assert stored.requests_today == 10


async def test_compare_and_swap_lets_exactly_one_concurrent_caller_win(db_engine, test_user):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    key = await _create_key(factory, test_user.id, daily_limit=100)

    async def swap():
        async with factory() as session:
            return await APIKeyRepository(session).compare_and_swap_status(
                key.id,
                user_id=test_user.id,
                expected_status=KeyStatus.ACTIVE,
                new_status=KeyStatus.COOLDOWN,
            )

    results = await asyncio.gather(*(swap() for _ in range(20)))

    assert sum(result is not None for result in results) == 1


async def test_unique_index_rejects_same_hash_but_allows_nulls(db_engine, test_user):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    await _create_key(factory, test_user.id, 10, key_hash="same")
    await _create_key(factory, test_user.id, 10, key_hash=None)
    await _create_key(factory, test_user.id, 10, key_hash=None)

    with pytest.raises(DuplicateKeyError):
        await _create_key(factory, test_user.id, 10, key_hash="same")


async def test_concurrent_bulk_creates_never_store_duplicates(db_engine, test_user, redis_client):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    raw_keys = " ".join(f"raw-key-{i}" for i in range(15))

    async def bulk():
        async with factory() as session:
            service = KeyPoolService(
                APIKeyRepository(session),
                KeyStatusCache(redis_client, ttl_seconds=30),
                RoundRobinSelector(redis_client),
            )
            return await service.create_keys_bulk(
                test_user.id,
                APIKeyBulkCreate(
                    provider=ProviderType.GEMINI, raw_keys=raw_keys, label_prefix="B", daily_limit=10
                ),
            )

    results = await asyncio.gather(bulk(), bulk(), bulk())

    assert sum(len(r.created) for r in results) == 15
    assert all(r.errors == [] for r in results)
    async with factory() as session:
        stored = await APIKeyRepository(session).list_all(user_id=test_user.id)
    assert len(stored) == 15
    assert len({k.key_hash for k in stored}) == 15
