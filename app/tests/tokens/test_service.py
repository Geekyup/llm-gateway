import pytest

from app.tokens.repository import GatewayTokenRepository
from app.tokens.schemas import GatewayTokenCreate
from app.tokens.service import GatewayTokenService


@pytest.fixture
def token_service(db_session):
    return GatewayTokenService(GatewayTokenRepository(db_session))


@pytest.mark.asyncio
async def test_create_token_returns_plaintext_once(token_service, test_user):
    created = await token_service.create_token(test_user.id, GatewayTokenCreate(label="my-app"))

    assert created.plaintext.startswith("gwk_")
    assert created.token.label == "my-app"
    assert created.token.is_active is True


@pytest.mark.asyncio
async def test_authenticate_resolves_to_owning_user(token_service, test_user):
    created = await token_service.create_token(test_user.id, GatewayTokenCreate(label="my-app"))

    resolved_user_id = await token_service.authenticate(created.plaintext)

    assert resolved_user_id == test_user.id


@pytest.mark.asyncio
async def test_authenticate_never_confuses_two_users_tokens(token_service, test_user, other_user):
    mine = await token_service.create_token(test_user.id, GatewayTokenCreate(label="mine"))
    theirs = await token_service.create_token(other_user.id, GatewayTokenCreate(label="theirs"))

    assert await token_service.authenticate(mine.plaintext) == test_user.id
    assert await token_service.authenticate(theirs.plaintext) == other_user.id


@pytest.mark.asyncio
async def test_authenticate_rejects_unknown_token(token_service):
    assert await token_service.authenticate("gwk_not-a-real-token") is None


@pytest.mark.asyncio
async def test_authenticate_rejects_revoked_token(token_service, test_user):
    created = await token_service.create_token(test_user.id, GatewayTokenCreate(label="my-app"))
    await token_service.set_active(created.token.id, test_user.id, is_active=False)

    assert await token_service.authenticate(created.plaintext) is None


@pytest.mark.asyncio
async def test_set_active_cannot_touch_another_users_token(token_service, test_user, other_user):
    theirs = await token_service.create_token(other_user.id, GatewayTokenCreate(label="theirs"))

    from app.core.exceptions import GatewayTokenNotFoundError

    with pytest.raises(GatewayTokenNotFoundError):
        await token_service.set_active(theirs.token.id, test_user.id, is_active=False)

    assert await token_service.authenticate(theirs.plaintext) == other_user.id


@pytest.mark.asyncio
async def test_delete_cannot_touch_another_users_token(token_service, test_user, other_user):
    theirs = await token_service.create_token(other_user.id, GatewayTokenCreate(label="theirs"))

    from app.core.exceptions import GatewayTokenNotFoundError

    with pytest.raises(GatewayTokenNotFoundError):
        await token_service.delete_token(theirs.token.id, test_user.id)

    assert await token_service.authenticate(theirs.plaintext) == other_user.id


@pytest.mark.asyncio
async def test_list_tokens_only_returns_own_tokens(token_service, test_user, other_user):
    await token_service.create_token(test_user.id, GatewayTokenCreate(label="mine"))
    await token_service.create_token(other_user.id, GatewayTokenCreate(label="theirs"))

    tokens = await token_service.list_tokens(test_user.id)

    assert [t.label for t in tokens] == ["mine"]
