from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from llm_gateway.core.exceptions import GatewayTokenNotFoundError
from llm_gateway.tokens.models import GatewayToken


class GatewayTokenRepository:
    """Pure persistence layer for GatewayToken — no hashing, no plaintext handling."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, user_id: int, label: str, token_hash: str, token_preview: str) -> GatewayToken:
        token = GatewayToken(
            user_id=user_id, label=label, token_hash=token_hash, token_preview=token_preview, is_active=True
        )
        self._session.add(token)
        await self._session.commit()
        await self._session.refresh(token)
        return token

    async def get(self, token_id: int, *, user_id: int) -> GatewayToken:
        """Scoped to the owner — a token belonging to someone else looks
        identical to a nonexistent one from the caller's point of view.
        """
        stmt = select(GatewayToken).where(GatewayToken.id == token_id, GatewayToken.user_id == user_id)
        result = await self._session.execute(stmt)
        token = result.scalar_one_or_none()
        if token is None:
            raise GatewayTokenNotFoundError(token_id)
        return token

    async def get_by_hash(self, token_hash: str) -> GatewayToken | None:
        """Deliberately NOT user_id-scoped: this is how an inbound /v1/*
        request's bearer token gets resolved to its owning user in the
        first place — see GatewayTokenService.authenticate.
        """
        stmt = select(GatewayToken).where(GatewayToken.token_hash == token_hash)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self, *, user_id: int) -> list[GatewayToken]:
        stmt = select(GatewayToken).where(GatewayToken.user_id == user_id).order_by(GatewayToken.id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def set_active(self, token_id: int, is_active: bool, *, user_id: int) -> GatewayToken:
        token = await self.get(token_id, user_id=user_id)
        token.is_active = is_active
        await self._session.commit()
        await self._session.refresh(token)
        return token

    async def delete(self, token_id: int, *, user_id: int) -> None:
        token = await self.get(token_id, user_id=user_id)
        await self._session.delete(token)
        await self._session.commit()

    async def touch_last_used(self, token_id: int) -> None:
        stmt = (
            update(GatewayToken)
            .where(GatewayToken.id == token_id)
            .values(last_used_at=datetime.now(timezone.utc))
            .execution_options(synchronize_session=False)
        )
        await self._session.execute(stmt)
        await self._session.commit()
