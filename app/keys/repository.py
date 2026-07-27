from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import KeyNotFoundError
from app.keys.enums import KeyStatus, ProviderType
from app.keys.models import APIKey


class APIKeyRepository:
    """Pure persistence layer — no caching, no business rules about cooldowns.

    Higher-level orchestration (deciding *when* a key should move to
    cooldown, how long, etc.) belongs in KeyPoolService.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: int,
        label: str,
        provider: ProviderType,
        key_encrypted: str,
        daily_limit: int,
        model: str | None = None,
    ) -> APIKey:
        key = APIKey(
            user_id=user_id,
            label=label,
            provider=provider,
            key_encrypted=key_encrypted,
            daily_limit=daily_limit,
            model=model,
            status=KeyStatus.ACTIVE,
        )
        self._session.add(key)
        await self._session.commit()
        await self._session.refresh(key)
        return key

    async def get(self, key_id: int, *, user_id: int) -> APIKey:
        """Looks up a key by id, scoped to its owner.

        A key that exists but belongs to someone else is indistinguishable
        from one that doesn't exist at all — both raise KeyNotFoundError, so
        callers never learn whether an id belongs to another account.
        """
        stmt = select(APIKey).where(APIKey.id == key_id, APIKey.user_id == user_id)
        result = await self._session.execute(stmt)
        key = result.scalar_one_or_none()
        if key is None:
            raise KeyNotFoundError(key_id=key_id)
        return key

    async def list_all(self, *, user_id: int, provider: ProviderType | None = None) -> list[APIKey]:
        stmt = select(APIKey).where(APIKey.user_id == user_id).order_by(APIKey.id)
        if provider is not None:
            stmt = stmt.where(APIKey.provider == provider)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_all_system_wide(self, *, provider: ProviderType | None = None) -> list[APIKey]:
        """Unscoped listing across every user's keys.

        Only for scheduled system jobs (housekeeping) that must walk the
        whole table — never expose this through an HTTP endpoint, or a
        request handler could enumerate other accounts' keys.
        """
        stmt = select(APIKey).order_by(APIKey.id)
        if provider is not None:
            stmt = stmt.where(APIKey.provider == provider)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_active(self, *, user_id: int, provider: ProviderType) -> list[APIKey]:
        stmt = select(APIKey).where(
            APIKey.user_id == user_id,
            APIKey.provider == provider,
            APIKey.status == KeyStatus.ACTIVE,
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_fields(self, key_id: int, *, user_id: int, **fields) -> APIKey:
        key = await self.get(key_id, user_id=user_id)
        for field, value in fields.items():
            setattr(key, field, value)
        await self._session.commit()
        await self._session.refresh(key)
        return key

    async def delete(self, key_id: int, *, user_id: int) -> None:
        key = await self.get(key_id, user_id=user_id)
        await self._session.delete(key)
        await self._session.commit()

    async def mark_status(
        self,
        key_id: int,
        status: KeyStatus,
        *,
        user_id: int,
        cooldown_until: datetime | None = None,
    ) -> APIKey:
        return await self.update_fields(key_id, user_id=user_id, status=status, cooldown_until=cooldown_until)

    async def increment_usage(self, key_id: int, *, user_id: int) -> None:
        stmt = (
            update(APIKey)
            .where(APIKey.id == key_id, APIKey.user_id == user_id)
            .values(
                requests_today=APIKey.requests_today + 1,
                last_used_at=datetime.now(UTC),
            )
            .execution_options(synchronize_session="fetch")
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def reset_daily_counters(self, *, provider: ProviderType | None = None) -> list[APIKey]:
        """Housekeeping: zero out requests_today and revive ACTIVE-eligible keys.

        Runs across all users deliberately — this is a scheduled system job
        (ARQ housekeeping), not something triggered by any one account, so
        it is the one place in this repository that isn't user_id-scoped.
        Returns the affected rows (not just a count) so the caller can
        invalidate each (user_id, provider) cache entry precisely. Keys
        with status=DISABLED are left untouched — that's a manual admin
        decision, not a daily reset.
        """
        select_stmt = select(APIKey).where(
            APIKey.status.in_([KeyStatus.COOLDOWN, KeyStatus.EXHAUSTED, KeyStatus.ACTIVE])
        )
        if provider is not None:
            select_stmt = select_stmt.where(APIKey.provider == provider)
        result = await self._session.execute(select_stmt)
        affected = list(result.scalars().all())
        if not affected:
            return []

        update_stmt = (
            update(APIKey)
            .where(APIKey.id.in_([key.id for key in affected]))
            .values(requests_today=0, status=KeyStatus.ACTIVE, cooldown_until=None)
            .execution_options(synchronize_session="fetch")
        )
        await self._session.execute(update_stmt)
        await self._session.commit()
        for key in affected:
            key.requests_today = 0
            key.status = KeyStatus.ACTIVE
            key.cooldown_until = None
        return affected

    async def clear_expired_cooldowns(self, *, now: datetime | None = None) -> list[APIKey]:
        """Housekeeping: bring keys back to ACTIVE once their cooldown window has passed.

        Returns the affected rows (not just a count) so the caller can
        invalidate each (user_id, provider) cache entry precisely instead
        of flushing every user's cache.
        """
        now = now or datetime.now(UTC)
        select_stmt = select(APIKey).where(APIKey.status == KeyStatus.COOLDOWN, APIKey.cooldown_until <= now)
        result = await self._session.execute(select_stmt)
        affected = list(result.scalars().all())
        if not affected:
            return []

        update_stmt = (
            update(APIKey)
            .where(APIKey.id.in_([key.id for key in affected]))
            .values(status=KeyStatus.ACTIVE, cooldown_until=None)
            # "evaluate" (the default) tries to re-check the WHERE clause against
            # in-session objects in pure Python, which chokes on tz-naive vs
            # tz-aware datetimes depending on backend (e.g. SQLite). "fetch"
            # re-selects matched rows from the DB instead — correct on every
            # backend and only marginally more expensive for a housekeeping job.
            .execution_options(synchronize_session="fetch")
        )
        await self._session.execute(update_stmt)
        await self._session.commit()
        for key in affected:
            key.status = KeyStatus.ACTIVE
            key.cooldown_until = None
        return affected
