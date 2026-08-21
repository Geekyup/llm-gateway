import hashlib
import logging
import re
from datetime import UTC, datetime, timedelta

from app.core.security import decrypt_key, encrypt_key
from app.keys.cache import KeyStatusCache
from app.keys.enums import KeyStatus, ProviderType
from app.keys.models import APIKey
from app.keys.repository import APIKeyRepository
from app.keys.schemas import (
    APIKeyBulkCreate,
    APIKeyBulkCreateError,
    APIKeyBulkCreateResult,
    APIKeyCreate,
    APIKeyDTO,
    APIKeyHealthCheckResult,
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

    async def reset_cooldown(self, key_id: int, user_id: int):
        key = await self._repo.mark_status(key_id, KeyStatus.ACTIVE, user_id=user_id, cooldown_until=None)
        await self._cache.invalidate(user_id, key.provider.value)
        return key

    async def delete_key(self, key_id: int, user_id: int) -> None:
        key = await self._repo.get(key_id, user_id=user_id)
        await self._cache.invalidate(user_id, key.provider.value)
        await self._repo.delete(key_id, user_id=user_id)

    _ALL_PROVIDERS_CACHE_KEY = "__all__"
    _NO_MODEL_NAMESPACE_SUFFIX = "__nomodel__"

    @staticmethod
    def _is_under_daily_limit(key: APIKeyDTO) -> bool:
        return key.requests_today < key.daily_limit

    async def get_candidate_keys(
        self, user_id: int, provider: ProviderType | None = None, model: str | None = None
    ) -> list[APIKeyDTO]:
        cache_namespace = provider.value if provider is not None else self._ALL_PROVIDERS_CACHE_KEY
        cached = await self._cache.get_active(user_id, cache_namespace)
        if cached is not None:
            all_active = cached
        else:
            keys = await self._repo.list_active(user_id=user_id, provider=provider)
            all_active = [APIKeyDTO.model_validate(k) for k in keys]
            await self._cache.set_active(user_id, cache_namespace, all_active)

        under_limit = [k for k in all_active if self._is_under_daily_limit(k)]

        if model is None:
            return under_limit

        return [k for k in under_limit if k.model is None or k.model == model]

    def _selector_namespace(self, provider: ProviderType | None, model: str | None) -> str:
        base = provider.value if provider is not None else self._ALL_PROVIDERS_CACHE_KEY
        model_part = model if model is not None else self._NO_MODEL_NAMESPACE_SUFFIX
        return f"{base}:{model_part}"

    async def select_key(
        self, user_id: int, provider: ProviderType | None = None, model: str | None = None
    ) -> APIKeyDTO | None:
        candidates = await self.get_candidate_keys(user_id, provider, model=model)
        selector_namespace = self._selector_namespace(provider, model)
        chosen = await self._selector.select(user_id, selector_namespace, candidates)
        if chosen is None:
            return None

        key_row = await self._repo.get(chosen.id, user_id=user_id)
        return APIKeyDTO.model_validate(key_row).model_copy(
            update={"decrypted_key": decrypt_key(key_row.key_encrypted)}
        )

    async def record_success(self, key_id: int, user_id: int, provider: ProviderType) -> None:
        await self._repo.increment_usage(key_id, user_id=user_id)
        await self._cache.invalidate(user_id, provider.value)

    async def record_rate_limited(
        self,
        key_id: int,
        user_id: int,
        provider: ProviderType,
        *,
        cooldown_seconds: int = 3600,
    ) -> None:
        cooldown_until = datetime.now(UTC) + timedelta(seconds=cooldown_seconds)
        await self._repo.mark_status(key_id, KeyStatus.COOLDOWN, user_id=user_id, cooldown_until=cooldown_until)
        await self._cache.invalidate(user_id, provider.value)
        logger.warning("user_id=%s key_id=%s provider=%s -> COOLDOWN until %s", user_id, key_id, provider, cooldown_until)

    async def record_exhausted(self, key_id: int, user_id: int, provider: ProviderType) -> None:
        await self._repo.mark_status(key_id, KeyStatus.EXHAUSTED, user_id=user_id)
        await self._cache.invalidate(user_id, provider.value)
        logger.warning("user_id=%s key_id=%s provider=%s -> EXHAUSTED", user_id, key_id, provider)

    async def check_key_health(self, key_id: int, user_id: int) -> APIKeyHealthCheckResult:
        key_row = await self._repo.get(key_id, user_id=user_id)
        provider = get_provider(key_row.provider.value)
        decrypted = decrypt_key(key_row.key_encrypted)

        result = await provider.health_check(decrypted)

        if result.ok:
            if key_row.status != KeyStatus.DISABLED:
                await self._repo.mark_status(key_id, KeyStatus.ACTIVE, user_id=user_id, cooldown_until=None)
                await self._cache.invalidate(user_id, key_row.provider.value)
            logger.info("health_check user_id=%s key_id=%s provider=%s -> ok", user_id, key_id, key_row.provider.value)
        else:
            if key_row.status not in (KeyStatus.DISABLED, KeyStatus.COOLDOWN):
                await self._repo.mark_status(key_id, KeyStatus.EXHAUSTED, user_id=user_id)
                await self._cache.invalidate(user_id, key_row.provider.value)
            logger.warning(
                "health_check user_id=%s key_id=%s provider=%s -> failed: %s",
                user_id, key_id, key_row.provider.value, result.detail,
            )

        return APIKeyHealthCheckResult(key_id=key_id, ok=result.ok, detail=result.detail)

    async def check_all_keys(self, user_id: int, provider: ProviderType | None = None) -> list[APIKeyHealthCheckResult]:
        keys = await self._repo.list_all(user_id=user_id, provider=provider)
        results: list[APIKeyHealthCheckResult] = []
        for key in keys:
            if key.status == KeyStatus.DISABLED:
                continue
            results.append(await self.check_key_health(key.id, user_id))
        return results

    async def clear_expired_cooldowns(self) -> list[APIKey]:
        revived = await self._repo.clear_expired_cooldowns()
        touched = {(key.user_id, key.provider.value) for key in revived}
        for user_id, provider_value in touched:
            await self._cache.invalidate(user_id, provider_value)
        return revived

    async def reset_daily_counters(self, provider: ProviderType | None = None) -> list[APIKey]:
        reset_keys = await self._repo.reset_daily_counters(provider=provider)
        touched = {(key.user_id, key.provider.value) for key in reset_keys}
        for user_id, provider_value in touched:
            await self._cache.invalidate(user_id, provider_value)
        return reset_keys