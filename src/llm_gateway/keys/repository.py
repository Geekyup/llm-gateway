from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from llm_gateway.core.exceptions import KeyNotFoundError
from llm_gateway.keys.enums import KeyStatus, ProviderType
from llm_gateway.keys.models import APIKey


class APIKeyRepository:
    """Pure persistence layer — no caching, no business rules about cooldowns.

    Higher-level orchestration (deciding *when* a key should move to
    cooldown, how long, etc.) belongs in KeyPoolService.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, label: str, provider: ProviderType, key_encrypted: str, daily_limit: int) -> APIKey:
        key = APIKey(
            label=label,
            provider=provider,
            key_encrypted=key_encrypted,
            daily_limit=daily_limit,
            status=KeyStatus.ACTIVE,
        )
        self._session.add(key)
        await self._session.commit()
        await self._session.refresh(key)
        return key

    async def get(self, key_id: int) -> APIKey:
        key = await self._session.get(APIKey, key_id)
        if key is None:
            raise KeyNotFoundError(key_id)
        return key

    async def list_all(self, *, provider: ProviderType | None = None) -> list[APIKey]:
        stmt = select(APIKey).order_by(APIKey.id)
        if provider is not None:
            stmt = stmt.where(APIKey.provider == provider)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_active(self, *, provider: ProviderType) -> list[APIKey]:
        stmt = select(APIKey).where(
            APIKey.provider == provider,
            APIKey.status == KeyStatus.ACTIVE,
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_fields(self, key_id: int, **fields) -> APIKey:
        key = await self.get(key_id)
        for field, value in fields.items():
            setattr(key, field, value)
        await self._session.commit()
        await self._session.refresh(key)
        return key

    async def mark_status(
        self,
        key_id: int,
        status: KeyStatus,
        *,
        cooldown_until: datetime | None = None,
    ) -> APIKey:
        return await self.update_fields(key_id, status=status, cooldown_until=cooldown_until)

    async def increment_usage(self, key_id: int) -> None:
        stmt = (
            update(APIKey)
            .where(APIKey.id == key_id)
            .values(
                requests_today=APIKey.requests_today + 1,
                last_used_at=datetime.now(timezone.utc),
            )
            .execution_options(synchronize_session="fetch")
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def reset_daily_counters(self, *, provider: ProviderType | None = None) -> int:
        """Housekeeping: zero out requests_today and revive ACTIVE-eligible keys.

        Returns the number of rows affected. Keys with status=DISABLED are
        left untouched — that's a manual admin decision, not a daily reset.
        """
        stmt = (
            update(APIKey)
            .where(APIKey.status.in_([KeyStatus.COOLDOWN, KeyStatus.EXHAUSTED, KeyStatus.ACTIVE]))
            .values(requests_today=0, status=KeyStatus.ACTIVE, cooldown_until=None)
            .execution_options(synchronize_session="fetch")
        )
        if provider is not None:
            stmt = stmt.where(APIKey.provider == provider)
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.rowcount or 0

    async def clear_expired_cooldowns(self, *, now: datetime | None = None) -> int:
        """Housekeeping: bring keys back to ACTIVE once their cooldown window has passed."""
        now = now or datetime.now(timezone.utc)
        stmt = (
            update(APIKey)
            .where(APIKey.status == KeyStatus.COOLDOWN, APIKey.cooldown_until <= now)
            .values(status=KeyStatus.ACTIVE, cooldown_until=None)
            # "evaluate" (the default) tries to re-check the WHERE clause against
            # in-session objects in pure Python, which chokes on tz-naive vs
            # tz-aware datetimes depending on backend (e.g. SQLite). "fetch"
            # re-selects matched rows from the DB instead — correct on every
            # backend and only marginally more expensive for a housekeeping job.
            .execution_options(synchronize_session="fetch")
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.rowcount or 0
