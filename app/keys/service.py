import asyncio
import hashlib
import logging
import re
from collections import defaultdict
from collections.abc import Sequence
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
from app.providers.base import HealthCheckResult
from app.providers.registry import get_provider

logger = logging.getLogger(__name__)

DEFAULT_COOLDOWN_SECONDS = 60


class KeyPoolService:
    def __init__(
        self,
        repository: APIKeyRepository,
        cache: KeyStatusCache,
        selector: KeySelector,
        *,
        cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS,
    ) -> None:
        self._repo = repository
        self._cache = cache
        self._selector = selector
        self._cooldown_seconds = cooldown_seconds

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

    async def list_all_keys_system_wide(
        self,
        provider: ProviderType | None = None,
        status: KeyStatus | None = None,
    ):
        return await self._repo.list_all_system_wide(provider=provider, status=status)

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

    async def delete_key(self, key_id: int, user_id: int) -> None:
        key = await self._repo.get(key_id, user_id=user_id)
        provider = key.provider
        await self._repo.delete(key_id, user_id=user_id)
        await self._cache.invalidate(user_id, provider.value)

    async def clear_expired_cooldowns(self):
        return await self._repo.clear_expired_cooldowns()

    async def reset_daily_counters(self, provider: ProviderType | None = None):
        return await self._repo.reset_daily_counters(provider=provider)

    async def get_candidate_keys(
        self,
        user_id: int,
        provider: ProviderType,
        *,
        model: str | None = None,
    ) -> list[APIKeyDTO]:
        active = await self._cache.get_active(user_id, provider.value)
        if active is None:
            rows = await self._repo.list_active(user_id=user_id, provider=provider)
            active = [
                APIKeyDTO(
                    id=row.id,
                    user_id=row.user_id,
                    label=row.label,
                    provider=row.provider,
                    status=row.status,
                    requests_today=row.requests_today,
                    daily_limit=row.daily_limit,
                    model=row.model,
                    decrypted_key=decrypt_key(row.key_encrypted),
                )
                for row in rows
            ]
            await self._cache.set_active(user_id, provider.value, active)

        if model is None:
            return active
        return [dto for dto in active if dto.model is None or dto.model == model]

    async def select_key(
        self,
        user_id: int,
        provider: ProviderType,
        *,
        model: str | None = None,
    ) -> APIKeyDTO | None:
        candidates = await self.get_candidate_keys(user_id, provider, model=model)
        return await self._selector.select(user_id, provider.value, candidates)

    async def record_success(self, key_id: int, user_id: int, provider: ProviderType) -> bool:
        recorded = await self._repo.increment_usage(key_id, user_id=user_id)
        await self._cache.invalidate(user_id, provider.value)
        return recorded

    async def record_invalid(self, key_id: int, user_id: int, provider: ProviderType):
        key = await self._repo.mark_status(key_id, KeyStatus.DISABLED, user_id=user_id)
        await self._cache.invalidate(user_id, provider.value)
        return key

    async def record_exhausted(self, key_id: int, user_id: int, provider: ProviderType):
        key = await self._repo.mark_status(key_id, KeyStatus.EXHAUSTED, user_id=user_id)
        await self._cache.invalidate(user_id, provider.value)
        return key

    async def record_rate_limited(self, key_id: int, user_id: int, provider: ProviderType):
        cooldown_until = datetime.now(UTC) + timedelta(seconds=self._cooldown_seconds)
        key = await self._repo.mark_status(
            key_id, KeyStatus.COOLDOWN, user_id=user_id, cooldown_until=cooldown_until
        )
        await self._cache.invalidate(user_id, provider.value)
        return key

    async def check_key_health(self, key_id: int, user_id: int) -> APIKeyHealthCheckResult:
        key = await self._repo.get(key_id, user_id=user_id)
        result = await self._probe_key(key)
        return await self._apply_health_result(key, result)

    async def check_all_keys(
        self, user_id: int, provider: ProviderType | None = None
    ) -> list[APIKeyHealthCheckResult]:
        keys = await self._repo.list_all(user_id=user_id, provider=provider)
        return [await self.check_key_health(key.id, user_id) for key in keys if key.status != KeyStatus.DISABLED]

    async def check_keys(
        self,
        keys: Sequence[APIKey],
        *,
        concurrency: int = 1,
        delay_seconds: float = 0.0,
    ) -> list[APIKeyHealthCheckResult]:
        by_provider: dict[ProviderType, list[APIKey]] = defaultdict(list)
        for key in keys:
            by_provider[key.provider].append(key)

        probed_per_provider = await asyncio.gather(
            *(
                self._probe_provider_keys(group, concurrency=concurrency, delay_seconds=delay_seconds)
                for group in by_provider.values()
            )
        )

        results: list[APIKeyHealthCheckResult] = []
        for probed in probed_per_provider:
            for key, probe_result in probed:
                results.append(await self._apply_health_result(key, probe_result))
        return results

    async def _probe_provider_keys(
        self,
        keys: Sequence[APIKey],
        *,
        concurrency: int,
        delay_seconds: float,
    ) -> list[tuple[APIKey, HealthCheckResult]]:
        semaphore = asyncio.Semaphore(concurrency)

        async def probe(key: APIKey) -> tuple[APIKey, HealthCheckResult]:
            async with semaphore:
                result = await self._probe_key(key)
                if delay_seconds:
                    await asyncio.sleep(delay_seconds)
                return key, result

        return list(await asyncio.gather(*(probe(key) for key in keys)))

    @staticmethod
    async def _probe_key(key: APIKey) -> HealthCheckResult:
        provider = get_provider(key.provider.value)
        return await provider.health_check(decrypt_key(key.key_encrypted))

    async def _apply_health_result(self, key: APIKey, result: HealthCheckResult) -> APIKeyHealthCheckResult:
        if key.status != KeyStatus.DISABLED:
            if result.ok:
                await self._repo.mark_status(key.id, KeyStatus.ACTIVE, user_id=key.user_id, cooldown_until=None)
                await self._cache.invalidate(key.user_id, key.provider.value)
            elif key.status != KeyStatus.COOLDOWN:
                await self._repo.mark_status(key.id, KeyStatus.EXHAUSTED, user_id=key.user_id)
                await self._cache.invalidate(key.user_id, key.provider.value)

        return APIKeyHealthCheckResult(key_id=key.id, ok=result.ok, detail=result.detail)
