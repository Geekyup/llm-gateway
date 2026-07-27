import logging
from datetime import UTC, datetime, timedelta

from app.auth.jwt import (
    TokenExpiredError,
    TokenPair,
    decode_token,
    hash_refresh_token,
    issue_token_pair,
)
from app.auth.models import User
from app.auth.repository import RefreshTokenRepository, UserRepository
from app.config import get_settings
from app.core.exceptions import InactiveUserError, TokenRevokedError

logger = logging.getLogger(__name__)


class AuthService:
    """Google-only auth: there is no password anywhere in this system.

    Every session starts at /auth/google/callback (see router.py), which
    calls login_with_google. Everything else here is just standard
    access/refresh-pair plumbing on top of that one identity source.
    """

    def __init__(self, user_repo: UserRepository, token_repo: RefreshTokenRepository) -> None:
        self._user_repo = user_repo
        self._token_repo = token_repo

    async def login_with_google(
        self, *, google_sub: str, email: str, display_name: str | None, avatar_url: str | None
    ) -> tuple[User, TokenPair]:
        user = await self._user_repo.get_by_google_sub(google_sub)
        if user is None:
            user = await self._user_repo.create(
                google_sub=google_sub, email=email, display_name=display_name, avatar_url=avatar_url
            )
        else:
            user = await self._user_repo.update_profile(
                user, email=email, display_name=display_name, avatar_url=avatar_url
            )

        if not user.is_active:
            raise InactiveUserError()

        return user, await self._issue_and_store(user.id)

    async def refresh(self, refresh_token: str) -> TokenPair:
        # decode_token raises TokenExpiredError/InvalidTokenError itself;
        # nothing extra to do here, so let them propagate to the caller.
        user_id = decode_token(refresh_token, expected_type="refresh")

        token_hash = hash_refresh_token(refresh_token)
        stored = await self._token_repo.get_by_hash(token_hash)

        if stored is None or stored.revoked:
            # Either an unknown token, or one we already rotated away from.
            # The latter is a strong reuse signal (e.g. a stolen refresh
            # token being replayed after the legitimate client already
            # rotated it) — burn every session for this user rather than
            # just rejecting the one request.
            await self._token_repo.revoke_all_for_user(user_id)
            raise TokenRevokedError()

        expires_at = stored.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at < datetime.now(UTC):
            raise TokenExpiredError()

        await self._token_repo.revoke(stored)
        return await self._issue_and_store(user_id)

    async def logout(self, refresh_token: str) -> None:
        stored = await self._token_repo.get_by_hash(hash_refresh_token(refresh_token))
        if stored is not None and not stored.revoked:
            await self._token_repo.revoke(stored)

    async def _issue_and_store(self, user_id: int) -> TokenPair:
        settings = get_settings()
        pair = issue_token_pair(user_id)
        now = datetime.now(UTC)
        await self._token_repo.create(
            user_id=user_id,
            token_hash=hash_refresh_token(pair.refresh_token),
            expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            created_at=now,
        )
        return pair
