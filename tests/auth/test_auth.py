from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from llm_gateway.auth.jwt import (
    InvalidTokenError,
    TokenExpiredError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_refresh_token,
)
from llm_gateway.auth.service import AuthService
from llm_gateway.core.exceptions import InactiveUserError, TokenRevokedError


# --- jwt.py ------------------------------------------------------------------

def test_access_and_refresh_tokens_carry_correct_type():
    access = create_access_token(user_id=42)
    refresh = create_refresh_token(user_id=42)

    assert decode_token(access, expected_type="access") == 42
    assert decode_token(refresh, expected_type="refresh") == 42


def test_access_token_rejected_when_refresh_expected():
    access = create_access_token(user_id=42)
    with pytest.raises(InvalidTokenError):
        decode_token(access, expected_type="refresh")


def test_garbage_token_raises_invalid():
    with pytest.raises(InvalidTokenError):
        decode_token("not-a-real-jwt", expected_type="access")


def test_hash_refresh_token_is_deterministic_and_one_way():
    token = "some-refresh-token-value"
    h1 = hash_refresh_token(token)
    h2 = hash_refresh_token(token)
    assert h1 == h2
    assert h1 != token


# --- repository.py -------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_create_and_get_by_google_sub(user_repo):
    user = await user_repo.create(
        google_sub="google-sub-123", email="vlad@example.com", display_name="Vlad", avatar_url=None
    )
    fetched = await user_repo.get_by_google_sub("google-sub-123")
    assert fetched is not None
    assert fetched.id == user.id
    assert fetched.email == "vlad@example.com"


@pytest.mark.asyncio
async def test_user_get_by_google_sub_missing_returns_none(user_repo):
    assert await user_repo.get_by_google_sub("nonexistent") is None


@pytest.mark.asyncio
async def test_update_profile_refreshes_display_fields(user_repo):
    user = await user_repo.create(
        google_sub="g1", email="old@example.com", display_name="Old Name", avatar_url=None
    )
    updated = await user_repo.update_profile(
        user, email="new@example.com", display_name="New Name", avatar_url="https://example.com/a.png"
    )
    assert updated.email == "new@example.com"
    assert updated.display_name == "New Name"
    assert updated.avatar_url == "https://example.com/a.png"


@pytest.mark.asyncio
async def test_refresh_token_create_and_lookup_by_hash(refresh_token_repo, user_repo):
    user = await user_repo.create(google_sub="g1", email="a@example.com", display_name=None, avatar_url=None)
    now = datetime.now(timezone.utc)
    token = await refresh_token_repo.create(
        user_id=user.id, token_hash="abc123", expires_at=now + timedelta(days=30), created_at=now
    )
    fetched = await refresh_token_repo.get_by_hash("abc123")
    assert fetched is not None
    assert fetched.id == token.id
    assert fetched.revoked is False


@pytest.mark.asyncio
async def test_revoke_all_for_user_only_touches_that_user(refresh_token_repo, user_repo):
    user_a = await user_repo.create(google_sub="a", email="a@example.com", display_name=None, avatar_url=None)
    user_b = await user_repo.create(google_sub="b", email="b@example.com", display_name=None, avatar_url=None)
    now = datetime.now(timezone.utc)

    token_a = await refresh_token_repo.create(
        user_id=user_a.id, token_hash="hash-a", expires_at=now + timedelta(days=30), created_at=now
    )
    token_b = await refresh_token_repo.create(
        user_id=user_b.id, token_hash="hash-b", expires_at=now + timedelta(days=30), created_at=now
    )

    await refresh_token_repo.revoke_all_for_user(user_a.id)

    assert (await refresh_token_repo.get_by_hash("hash-a")).revoked is True
    assert (await refresh_token_repo.get_by_hash("hash-b")).revoked is False


# --- service.py ----------------------------------------------------------------

@pytest.fixture
def auth_service(user_repo, refresh_token_repo):
    return AuthService(user_repo, refresh_token_repo)


@pytest.mark.asyncio
async def test_login_with_google_creates_new_user(auth_service, user_repo):
    user, pair = await auth_service.login_with_google(
        google_sub="new-sub", email="new@example.com", display_name="New User", avatar_url=None
    )
    assert user.google_sub == "new-sub"
    assert pair.access_token
    assert pair.refresh_token

    fetched = await user_repo.get_by_google_sub("new-sub")
    assert fetched is not None


@pytest.mark.asyncio
async def test_login_with_google_reuses_existing_user_and_updates_profile(auth_service, user_repo):
    await user_repo.create(google_sub="existing", email="old@example.com", display_name="Old", avatar_url=None)

    user, _ = await auth_service.login_with_google(
        google_sub="existing", email="new@example.com", display_name="New Name", avatar_url=None
    )
    assert user.email == "new@example.com"
    assert user.display_name == "New Name"

    # No duplicate row created for the same google_sub.
    all_users_with_sub = await user_repo.get_by_google_sub("existing")
    assert all_users_with_sub.id == user.id


@pytest.mark.asyncio
async def test_login_with_google_rejects_inactive_user(auth_service, user_repo):
    user = await user_repo.create(google_sub="inactive-sub", email="a@example.com", display_name=None, avatar_url=None)
    user.is_active = False
    await user_repo._session.commit()

    with pytest.raises(InactiveUserError):
        await auth_service.login_with_google(
            google_sub="inactive-sub", email="a@example.com", display_name=None, avatar_url=None
        )


@pytest.mark.asyncio
async def test_refresh_rotates_token_and_revokes_old_one(auth_service, refresh_token_repo):
    _, pair = await auth_service.login_with_google(
        google_sub="g1", email="a@example.com", display_name=None, avatar_url=None
    )

    new_pair = await auth_service.refresh(pair.refresh_token)
    assert new_pair.refresh_token != pair.refresh_token

    old_hash = hash_refresh_token(pair.refresh_token)
    old_stored = await refresh_token_repo.get_by_hash(old_hash)
    assert old_stored.revoked is True


@pytest.mark.asyncio
async def test_refresh_reuse_of_revoked_token_revokes_whole_session(auth_service, refresh_token_repo):
    _, pair = await auth_service.login_with_google(
        google_sub="g1", email="a@example.com", display_name=None, avatar_url=None
    )
    new_pair = await auth_service.refresh(pair.refresh_token)

    # Replaying the now-rotated-away-from token should be treated as
    # suspicious and burn the whole session, not just fail quietly.
    with pytest.raises(TokenRevokedError):
        await auth_service.refresh(pair.refresh_token)

    new_hash = hash_refresh_token(new_pair.refresh_token)
    stored = await refresh_token_repo.get_by_hash(new_hash)
    assert stored.revoked is True


@pytest.mark.asyncio
async def test_refresh_with_expired_token_raises(auth_service):
    with patch("llm_gateway.auth.jwt.get_settings") as mock_settings:
        mock_settings.return_value.JWT_SECRET_KEY = "test-jwt-secret-key"
        mock_settings.return_value.JWT_ALGORITHM = "HS256"
        mock_settings.return_value.REFRESH_TOKEN_EXPIRE_DAYS = -1  # already expired
        expired_refresh = create_refresh_token(user_id=1)

    with pytest.raises(TokenExpiredError):
        await auth_service.refresh(expired_refresh)


@pytest.mark.asyncio
async def test_logout_revokes_token(auth_service, refresh_token_repo):
    _, pair = await auth_service.login_with_google(
        google_sub="g1", email="a@example.com", display_name=None, avatar_url=None
    )
    await auth_service.logout(pair.refresh_token)

    stored = await refresh_token_repo.get_by_hash(hash_refresh_token(pair.refresh_token))
    assert stored.revoked is True


@pytest.mark.asyncio
async def test_logout_with_unknown_token_is_a_noop(auth_service):
    # Logging out with a token that was never issued shouldn't raise —
    # there's nothing to revoke, and the end state (not logged in) is
    # the same either way.
    await auth_service.logout("never-issued-token-value")
