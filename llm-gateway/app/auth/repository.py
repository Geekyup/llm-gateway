from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import RefreshToken, User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: int) -> User | None:
        result = await self._session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_google_sub(self, google_sub: str) -> User | None:
        result = await self._session.execute(select(User).where(User.google_sub == google_sub))
        return result.scalar_one_or_none()

    async def create(
        self, *, google_sub: str, email: str, display_name: str | None, avatar_url: str | None
    ) -> User:
        user = User(google_sub=google_sub, email=email, display_name=display_name, avatar_url=avatar_url)
        self._session.add(user)
        await self._session.commit()
        await self._session.refresh(user)
        return user

    async def update_profile(
        self, user: User, *, email: str, display_name: str | None, avatar_url: str | None
    ) -> User:
        # Refresh display fields from Google on every login — a person's
        # name/avatar/email can change on Google's side over time.
        user.email = email
        user.display_name = display_name
        user.avatar_url = avatar_url
        await self._session.commit()
        await self._session.refresh(user)
        return user


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, user_id: int, token_hash: str, expires_at: datetime, created_at: datetime) -> RefreshToken:
        token = RefreshToken(
            user_id=user_id, token_hash=token_hash, expires_at=expires_at, created_at=created_at
        )
        self._session.add(token)
        await self._session.commit()
        await self._session.refresh(token)
        return token

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        result = await self._session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def revoke(self, token: RefreshToken) -> None:
        token.revoked = True
        await self._session.commit()

    async def revoke_all_for_user(self, user_id: int) -> None:
        """Used on logout-everywhere and on reuse-detection (see AuthService.refresh)."""
        await self._session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
            .values(revoked=True)
        )
        await self._session.commit()
