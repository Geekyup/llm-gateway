import pytest

from app.core.exceptions import GatewayTokenNotFoundError


@pytest.mark.asyncio
async def test_create_and_get(token_repo, test_user):
    token = await token_repo.create(
        user_id=test_user.id, label="my-app", token_hash="hash1", token_preview="gwk_...ab12"
    )
    fetched = await token_repo.get(token.id, user_id=test_user.id)
    assert fetched.label == "my-app"
    assert fetched.is_active is True


@pytest.mark.asyncio
async def test_get_missing_raises(token_repo, test_user):
    with pytest.raises(GatewayTokenNotFoundError):
        await token_repo.get(999, user_id=test_user.id)


@pytest.mark.asyncio
async def test_get_other_users_token_raises(token_repo, test_user, other_user):
    """A token belonging to someone else must behave exactly like a
    nonexistent one — this is the isolation guarantee itself.
    """
    token = await token_repo.create(
        user_id=other_user.id, label="not-yours", token_hash="hash1", token_preview="gwk_...ab12"
    )
    with pytest.raises(GatewayTokenNotFoundError):
        await token_repo.get(token.id, user_id=test_user.id)


@pytest.mark.asyncio
async def test_list_all_excludes_other_users_tokens(token_repo, test_user, other_user):
    await token_repo.create(user_id=other_user.id, label="theirs", token_hash="h1", token_preview="p1")
    mine = await token_repo.create(user_id=test_user.id, label="mine", token_hash="h2", token_preview="p2")

    result = await token_repo.list_all(user_id=test_user.id)

    assert [t.id for t in result] == [mine.id]


@pytest.mark.asyncio
async def test_get_by_hash_is_not_user_scoped(token_repo, test_user):
    """get_by_hash is the one deliberately-unscoped lookup: it's how an
    inbound bearer token resolves to its owner in the first place.
    """
    token = await token_repo.create(user_id=test_user.id, label="mine", token_hash="hash1", token_preview="p1")

    found = await token_repo.get_by_hash("hash1")

    assert found is not None
    assert found.id == token.id
    assert found.user_id == test_user.id


@pytest.mark.asyncio
async def test_set_active_scoped_to_owner(token_repo, test_user, other_user):
    token = await token_repo.create(user_id=other_user.id, label="theirs", token_hash="h1", token_preview="p1")

    with pytest.raises(GatewayTokenNotFoundError):
        await token_repo.set_active(token.id, False, user_id=test_user.id)


@pytest.mark.asyncio
async def test_delete_scoped_to_owner(token_repo, test_user, other_user):
    token = await token_repo.create(user_id=other_user.id, label="theirs", token_hash="h1", token_preview="p1")

    with pytest.raises(GatewayTokenNotFoundError):
        await token_repo.delete(token.id, user_id=test_user.id)

    # Confirm it's untouched from the real owner's perspective.
    still_there = await token_repo.get(token.id, user_id=other_user.id)
    assert still_there.id == token.id
