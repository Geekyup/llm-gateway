import pytest

from app.core.exceptions import GatewayTokenNotFoundError
from app.tokens.cache import TokenAuthCache
from app.tokens.repository import GatewayTokenRepository
from app.tokens.schemas import GatewayTokenCreate
from app.tokens.service import GatewayTokenService


class _CountingRepository(GatewayTokenRepository):
    def __init__(self, session):
        super().__init__(session)
        self.lookups = 0
        self.touches = 0

    async def get_active_by_hash(self, token_hash):
        self.lookups += 1
        return await super().get_active_by_hash(token_hash)

    async def touch_last_used(self, token_id, *, stale_after):
        self.touches += 1
        await super().touch_last_used(token_id, stale_after=stale_after)


class _BrokenRedis:
    async def get(self, key):
        raise ConnectionError("redis is down")

    async def set(self, key, value, ex=None):
        raise ConnectionError("redis is down")

    async def delete(self, key):
        raise ConnectionError("redis is down")


@pytest.fixture
def repo(db_session):
    return _CountingRepository(db_session)


@pytest.fixture
def cached_service(repo, fake_redis):
    return GatewayTokenService(repo, TokenAuthCache(fake_redis, ttl_seconds=60))


@pytest.mark.asyncio
async def test_cache_roundtrip_and_delete(fake_redis):
    cache = TokenAuthCache(fake_redis, ttl_seconds=60)

    assert await cache.get("abc") is None
    await cache.set("abc", 7)
    assert await cache.get("abc") == 7
    await cache.delete("abc")
    assert await cache.get("abc") is None


@pytest.mark.asyncio
async def test_cache_swallows_redis_errors():
    cache = TokenAuthCache(_BrokenRedis(), ttl_seconds=60)

    assert await cache.get("abc") is None
    await cache.set("abc", 7)
    await cache.delete("abc")


@pytest.mark.asyncio
async def test_repeated_authentication_is_served_from_cache(cached_service, repo, test_user):
    created = await cached_service.create_token(test_user.id, GatewayTokenCreate(label="app"))

    assert await cached_service.authenticate(created.plaintext) == test_user.id
    assert await cached_service.authenticate(created.plaintext) == test_user.id
    assert await cached_service.authenticate(created.plaintext) == test_user.id

    assert repo.lookups == 1


@pytest.mark.asyncio
async def test_revoking_a_cached_token_takes_effect_immediately(cached_service, test_user):
    created = await cached_service.create_token(test_user.id, GatewayTokenCreate(label="app"))
    assert await cached_service.authenticate(created.plaintext) == test_user.id

    await cached_service.set_active(created.token.id, test_user.id, is_active=False)

    assert await cached_service.authenticate(created.plaintext) is None


@pytest.mark.asyncio
async def test_reactivated_token_authenticates_again(cached_service, test_user):
    created = await cached_service.create_token(test_user.id, GatewayTokenCreate(label="app"))
    await cached_service.authenticate(created.plaintext)
    await cached_service.set_active(created.token.id, test_user.id, is_active=False)

    await cached_service.set_active(created.token.id, test_user.id, is_active=True)

    assert await cached_service.authenticate(created.plaintext) == test_user.id


@pytest.mark.asyncio
async def test_deleting_a_cached_token_takes_effect_immediately(cached_service, test_user):
    created = await cached_service.create_token(test_user.id, GatewayTokenCreate(label="app"))
    assert await cached_service.authenticate(created.plaintext) == test_user.id

    await cached_service.delete_token(created.token.id, test_user.id)

    assert await cached_service.authenticate(created.plaintext) is None


@pytest.mark.asyncio
async def test_deleting_someone_elses_token_keeps_it_cached_and_valid(
    cached_service, test_user, other_user
):
    theirs = await cached_service.create_token(other_user.id, GatewayTokenCreate(label="theirs"))
    assert await cached_service.authenticate(theirs.plaintext) == other_user.id

    with pytest.raises(GatewayTokenNotFoundError):
        await cached_service.delete_token(theirs.token.id, test_user.id)

    assert await cached_service.authenticate(theirs.plaintext) == other_user.id


@pytest.mark.asyncio
async def test_unknown_token_is_never_cached(cached_service, fake_redis):
    assert await cached_service.authenticate("gwk_not-a-real-token") is None
    assert await cached_service.authenticate("gwk_not-a-real-token") is None

    assert fake_redis._store == {}


@pytest.mark.asyncio
async def test_authentication_survives_a_cache_outage(repo, test_user):
    service = GatewayTokenService(repo, TokenAuthCache(_BrokenRedis(), ttl_seconds=60))
    created = await service.create_token(test_user.id, GatewayTokenCreate(label="app"))

    assert await service.authenticate(created.plaintext) == test_user.id
    assert await service.authenticate(created.plaintext) == test_user.id
    assert repo.lookups == 2


@pytest.mark.asyncio
async def test_last_used_is_written_only_when_stale(repo, test_user):
    service = GatewayTokenService(repo)
    created = await service.create_token(test_user.id, GatewayTokenCreate(label="app"))

    for _ in range(4):
        assert await service.authenticate(created.plaintext) == test_user.id

    assert repo.touches == 1
