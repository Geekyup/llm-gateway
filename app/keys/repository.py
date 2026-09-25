from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import KeyNotFoundError
from app.keys.enums import KeyStatus, ProviderType
from app.keys.models import APIKey


class APIKeyRepository:
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

    async def get(self, key_id: int, user_id: int) -> APIKey:
        result = await self._session.execute(
            select(APIKey).where(APIKey.id == key_id, APIKey.user_id == user_id)
        )
        key = result.scalar_one_or_none()
        if key is None:
            raise KeyNotFoundError(key_id=key_id)
        return key

    async def list_all(self, user_id: int, provider: ProviderType | None = None) -> list[APIKey]:
        query = select(APIKey).where(APIKey.user_id == user_id).order_by(APIKey.id)
        if provider is not None:
            query = query.where(APIKey.provider == provider)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def list_all_system_wide(
        self,
        provider: ProviderType | None = None,
        status: KeyStatus | None = None,
    ) -> list[APIKey]:
        query = select(APIKey).order_by(APIKey.id)
        if provider is not None:
            query = query.where(APIKey.provider == provider)
        if status is not None:
            query = query.where(APIKey.status == status)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def list_active(self, user_id: int, provider: ProviderType | None = None) -> list[APIKey]:
        query = select(APIKey).where(
            APIKey.user_id == user_id,
            APIKey.status == KeyStatus.ACTIVE,
        )
        if provider is not None:
            query = query.where(APIKey.provider == provider)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def update_fields(self, key_id: int, user_id: int, **fields) -> APIKey:
        key = await self.get(key_id, user_id=user_id)
        for field, value in fields.items():
            setattr(key, field, value)
        await self._session.commit()
        await self._session.refresh(key)
        return key

    async def delete(self, key_id: int, user_id: int) -> None:
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

    async def increment_usage(self, key_id: int, user_id: int) -> bool:
        result = await self._session.execute(
            update(APIKey)
            .where(
                APIKey.id == key_id,
                APIKey.user_id == user_id,
                APIKey.requests_today < APIKey.daily_limit,
            )
            .values(
                requests_today=APIKey.requests_today + 1,
                last_used_at=datetime.now(UTC),
            )
            .execution_options(synchronize_session="fetch")
        )
        await self._session.commit()
        return result.rowcount > 0

    async def reset_daily_counters(self, provider: ProviderType | None = None) -> list[APIKey]:
        statement = (
            update(APIKey)
            .where(APIKey.status.in_([KeyStatus.COOLDOWN, KeyStatus.EXHAUSTED, KeyStatus.ACTIVE]))
            .values(requests_today=0, status=KeyStatus.ACTIVE, cooldown_until=None)
            .returning(APIKey)
            .execution_options(synchronize_session="fetch")
        )
        if provider is not None:
            statement = statement.where(APIKey.provider == provider)
        return await self._execute_bulk_update(statement)

    async def clear_expired_cooldowns(self, now: datetime | None = None) -> list[APIKey]:
        now = now or datetime.now(UTC)
        statement = (
            update(APIKey)
            .where(APIKey.status == KeyStatus.COOLDOWN, APIKey.cooldown_until <= now)
            .values(status=KeyStatus.ACTIVE, cooldown_until=None)
            .returning(APIKey)
            .execution_options(synchronize_session="fetch")
        )
        return await self._execute_bulk_update(statement)

    async def _execute_bulk_update(self, statement) -> list[APIKey]:
        result = await self._session.execute(statement)
        affected = list(result.scalars().all())
        await self._session.commit()
        return sorted(affected, key=lambda key: key.id)
