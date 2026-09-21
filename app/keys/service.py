import hashlib
import logging
import re

from app.core.security import decrypt_key, encrypt_key
from app.keys.cache import KeyStatusCache
from app.keys.enums import KeyStatus, ProviderType
from app.keys.repository import APIKeyRepository
from app.keys.schemas import (
    APIKeyBulkCreate,
    APIKeyBulkCreateError,
    APIKeyBulkCreateResult,
    APIKeyCreate,
    APIKeyUpdate,
)
from app.keys.selector import KeySelector
from app.providers.registry import get_provider

logger = logging.getLogger(__name__)


class KeyPoolService:
    def __init__(
        self,
        repository: APIKeyRepository,
        cache: KeyStatusCache,
        selector: KeySelector,
    ) -> None:
        self._repo = repository
        self._cache = cache
        self._selector = selector

    async def create_key(self, user_id: int, payload: APIKeyCreate):
        encrypted = encrypt_key(payload.raw_key)
        key = await self._repo.create(
            user_id=user_id,
            label=payload.label,
            provider=payload.provider,
            key_encrypted=encrypted,
            daily_limit=payload.daily_limit,
            model=payload.model,
        )
        await self._cache.invalidate(user_id, payload.provider.value)
        return key

    async def create_keys_bulk(self, user_id: int, payload: APIKeyBulkCreate) -> APIKeyBulkCreateResult:
        raw_candidates = [c.strip() for c in re.split(r"[\s,]+", payload.raw_keys) if c.strip()]

        seen_in_batch: set[str] = set()
        existing = await self._repo.list_all(user_id=user_id, provider=payload.provider)
        existing_raw_by_hash = {self._fingerprint(decrypt_key(k.key_encrypted)) for k in existing}

        created = []
        errors: list[APIKeyBulkCreateError] = []
        skipped_duplicates = 0
        seq = len(existing) + 1

        for raw_key in raw_candidates:
            fp = self._fingerprint(raw_key)
            if fp in seen_in_batch or fp in existing_raw_by_hash:
                skipped_duplicates += 1
                continue
            seen_in_batch.add(fp)

            try:
                key = await self._repo.create(
                    user_id=user_id,
                    label=f"{payload.label_prefix} {seq}",
                    provider=payload.provider,
                    key_encrypted=encrypt_key(raw_key),
                    daily_limit=payload.daily_limit,
                    model=payload.model,
                )
                created.append(key)
                seq += 1
            except Exception as exc:
                logger.warning("bulk key create failed: %s", exc)
                errors.append(
                    APIKeyBulkCreateError(
                        raw_key_preview=self._preview(raw_key),
                        detail=str(exc),
                    )
                )

        if created:
            await self._cache.invalidate(user_id, payload.provider.value)

        return APIKeyBulkCreateResult(
            created=created,
            skipped_duplicates=skipped_duplicates,
            errors=errors,
        )

    @staticmethod
    def _fingerprint(raw_key: str) -> str:
        return hashlib.sha256(raw_key.encode()).hexdigest()

    @staticmethod
    def _preview(raw_key: str) -> str:
        if len(raw_key) <= 8:
            return "***"
        return f"{raw_key[:4]}...{raw_key[-4:]}"

    async def list_keys(self, user_id: int, provider: ProviderType | None = None):
        return await self._repo.list_all(user_id=user_id, provider=provider)

    async def list_all_keys_system_wide(self, provider: ProviderType | None = None):
        return await self._repo.list_all_system_wide(provider=provider)

    async def get_key(self, key_id: int, user_id: int):
        return await self._repo.get(key_id, user_id=user_id)

    async def set_status(self, key_id: int, user_id: int, status: KeyStatus):
        key = await self._repo.mark_status(key_id, status, user_id=user_id)
        await self._cache.invalidate(user_id, key.provider.value)
        return key

    async def update_key(self, key_id: int, user_id: int, payload: APIKeyUpdate):
        fields = payload.model_dump(exclude_unset=True)
        if not fields:
            return await self._repo.get(key_id, user_id=user_id)

        if fields.get("status") is not None and fields["status"] != KeyStatus.COOLDOWN:
            fields.setdefault("cooldown_until", None)

        key = await self._repo.update_fields(key_id, user_id=user_id, **fields)
        await self._cache.invalidate(user_id, key.provider.value)
        return key

    async def list_models_for_key(self, key_id: int, user_id: int):
        key_row = await self._repo.get(key_id, user_id=user_id)
        provider = get_provider(key_row.provider.value)
        decrypted = decrypt_key(key_row.key_encrypted)
        return await provider.list_models(decrypted)

    async def reset_cooldown(self, key_id: int, user_id: int):
        key = await self._repo.mark_status(key_id, KeyStatus.ACTIVE, user_id=user_id, cooldown_until=None)
        await self._cache.invalidate(user_id, key.provider.value)
        return key
