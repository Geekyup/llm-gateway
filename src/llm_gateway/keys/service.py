import logging
from datetime import datetime, timedelta, timezone

from llm_gateway.core.security import decrypt_key, encrypt_key
from llm_gateway.keys.cache import KeyStatusCache
from llm_gateway.keys.enums import KeyStatus, ProviderType
from llm_gateway.keys.repository import APIKeyRepository
from llm_gateway.keys.schemas import APIKeyCreate, APIKeyDTO, APIKeyUpdate
from llm_gateway.keys.selector import KeySelector

logger = logging.getLogger(__name__)


class KeyPoolService:
    """Public API for everything gateway/admin code needs from the key pool.

    Callers never touch APIKeyRepository, KeyStatusCache or KeySelector
    directly — this is the seam that keeps Redis/Postgres details out of
    the gateway proxy logic.
    """

    def __init__(
        self,
        repository: APIKeyRepository,
        cache: KeyStatusCache,
        selector: KeySelector,
    ) -> None:
        self._repo = repository
        self._cache = cache
        self._selector = selector

    # --- admin-facing CRUD -------------------------------------------------

    async def create_key(self, payload: APIKeyCreate):
        encrypted = encrypt_key(payload.raw_key)
        key = await self._repo.create(
            label=payload.label,
            provider=payload.provider,
            key_encrypted=encrypted,
            daily_limit=payload.daily_limit,
        )
        await self._cache.invalidate(payload.provider.value)
        return key  # ORM row — admin router serializes via APIKeyRead.model_validate

    async def list_keys(self, *, provider: ProviderType | None = None):
        return await self._repo.list_all(provider=provider)  # ORM rows

    async def set_status(self, key_id: int, status: KeyStatus):
        key = await self._repo.mark_status(key_id, status)
        await self._cache.invalidate(key.provider.value)
        return key  # ORM row

    async def update_key(self, key_id: int, payload: APIKeyUpdate):
        fields = payload.model_dump(exclude_unset=True)
        if not fields:
            return await self._repo.get(key_id)

        # Clear an explicit cooldown timestamp whenever status moves away
        # from COOLDOWN via a plain update (e.g. admin re-activating a key).
        if fields.get("status") is not None and fields["status"] != KeyStatus.COOLDOWN:
            fields.setdefault("cooldown_until", None)

        key = await self._repo.update_fields(key_id, **fields)
        await self._cache.invalidate(key.provider.value)
        return key  # ORM row

    async def reset_cooldown(self, key_id: int):
        key = await self._repo.mark_status(key_id, KeyStatus.ACTIVE, cooldown_until=None)
        await self._cache.invalidate(key.provider.value)
        return key  # ORM row

    async def delete_key(self, key_id: int) -> None:
        key = await self._repo.get(key_id)
        await self._cache.invalidate(key.provider.value)
        await self._repo.delete(key_id)

    # --- gateway-facing hot path --------------------------------------------

    async def get_candidate_keys(self, provider: ProviderType) -> list[APIKeyDTO]:
        """ACTIVE key metadata for a provider, cache-first."""
        cached = await self._cache.get_active(provider.value)
        if cached is not None:
            return cached

        keys = await self._repo.list_active(provider=provider)
        dtos = [APIKeyDTO.model_validate(k) for k in keys]
        await self._cache.set_active(provider.value, dtos)
        return dtos

    async def select_key(self, provider: ProviderType) -> APIKeyDTO | None:
        """Pick the next candidate key (round-robin) and attach its decrypted secret.

        Returns None if the pool has no active key for this provider.
        """
        candidates = await self.get_candidate_keys(provider)
        chosen = await self._selector.select(provider.value, candidates)
        if chosen is None:
            return None

        # Decrypt fresh from the DB — never from cache/DTO in flight.
        key_row = await self._repo.get(chosen.id)
        return APIKeyDTO.model_validate(key_row).model_copy(
            update={"decrypted_key": decrypt_key(key_row.key_encrypted)}
        )

    async def record_success(self, key_id: int, provider: ProviderType) -> None:
        await self._repo.increment_usage(key_id)
        # Counter changed — invalidate so the next candidate fetch sees it.
        # (Cheap: TTL already bounds staleness, this just tightens it.)
        await self._cache.invalidate(provider.value)

    async def record_rate_limited(
        self,
        key_id: int,
        provider: ProviderType,
        *,
        cooldown_seconds: int = 3600,
    ) -> None:
        cooldown_until = datetime.now(timezone.utc) + timedelta(seconds=cooldown_seconds)
        await self._repo.mark_status(key_id, KeyStatus.COOLDOWN, cooldown_until=cooldown_until)
        await self._cache.invalidate(provider.value)
        logger.warning("key_id=%s provider=%s -> COOLDOWN until %s", key_id, provider, cooldown_until)

    async def record_exhausted(self, key_id: int, provider: ProviderType) -> None:
        await self._repo.mark_status(key_id, KeyStatus.EXHAUSTED)
        await self._cache.invalidate(provider.value)
        logger.warning("key_id=%s provider=%s -> EXHAUSTED", key_id, provider)
