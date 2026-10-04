import asyncio
import hashlib
import logging
import re
from collections.abc import Collection, Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import DuplicateKeyError
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
            key_hash=self._fingerprint(payload.raw_key),
            daily_limit=payload.daily_limit,
            model=payload.model,
        )
        await self._cache.invalidate(user_id, payload.provider.value)
        return key

    async def create_keys_bulk(self, user_id: int, payload: APIKeyBulkCreate) -> APIKeyBulkCreateResult:
        raw_candidates = [c.strip() for c in re.split(r"[\s,]+", payload.raw_keys) if c.strip()]

        existing = await self._repo.list_all(user_id=user_id, provider=payload.provider)
        known_hashes = {k.key_hash for k in existing if k.key_hash is not None}

        skipped_duplicates = 0
        pending: list[tuple[str, str]] = []
        for raw_key in raw_candidates:
            fingerprint = self._fingerprint(raw_key)
            if fingerprint in known_hashes:
                skipped_duplicates += 1
                continue
            known_hashes.add(fingerprint)
            pending.append((raw_key, fingerprint))

        def build_item(raw_key: str, fingerprint: str, seq: int) -> dict:
            return {
                "user_id": user_id,
                "label": f"{payload.label_prefix} {seq}",
                "provider": payload.provider,
                "key_encrypted": encrypt_key(raw_key),
                "key_hash": fingerprint,
                "daily_limit": payload.daily_limit,
                "model": payload.model,
            }

        first_seq = len(existing) + 1
        created = []
        errors: list[APIKeyBulkCreateError] = []

        if pending:
            try:
                created = await self._repo.create_many(
                    [build_item(raw, fp, first_seq + i) for i, (raw, fp) in enumerate(pending)]
                )
            except IntegrityError:
                logger.info("bulk key insert hit a concurrent duplicate, falling back to per-key inserts")
                seq = first_seq
                for raw_key, fingerprint in pending:
                    try:
                        created.append(await self._repo.create(**build_item(raw_key, fingerprint, seq)))
                        seq += 1
                    except DuplicateKeyError:
                        skipped_duplicates += 1
                    except Exception as exc:
                        logger.warning("bulk key create failed: %s", exc)
                        errors.append(
                            APIKeyBulkCreateError(raw_key_preview=self._preview(raw_key), detail=str(exc))
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

    async def _active_keys(self, user_id: int, provider: ProviderType) -> list[APIKeyDTO]:
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
                    key_encrypted=row.key_encrypted,
                )
                for row in rows
            ]
            await self._cache.set_active(user_id, provider.value, active)
        return active

    async def get_candidate_keys(
        self,
        user_id: int,
        provider: ProviderType | None,
        *,
        model: str | None = None,
        exclude_ids: Collection[int] = (),
    ) -> list[APIKeyDTO]:
        providers = [provider] if provider is not None else list(ProviderType)
        candidates: list[APIKeyDTO] = []
        for item in providers:
            candidates.extend(await self._active_keys(user_id, item))

        if model is not None:
            candidates = [dto for dto in candidates if dto.model is None or dto.model == model]
        if exclude_ids:
            candidates = [dto for dto in candidates if dto.id not in exclude_ids]
        return candidates

    async def select_key(
        self,
        user_id: int,
        provider: ProviderType | None,
        *,
        model: str | None = None,
        exclude_ids: Collection[int] = (),
    ) -> APIKeyDTO | None:
        candidates = await self.get_candidate_keys(
            user_id, provider, model=model, exclude_ids=exclude_ids
        )
        scope = provider.value if provider is not None else "any"
        return await self._selector.select(user_id, scope, candidates)

    async def record_success(self, key_id: int, user_id: int, provider: ProviderType) -> bool:
        key = await self._repo.increment_usage(key_id, user_id=user_id)
        if key is None:
            await self._cache.invalidate(user_id, provider.value)
            return False
        if key.requests_today >= key.daily_limit:
            await self._repo.compare_and_swap_status(
                key_id,
                user_id=user_id,
                expected_status=KeyStatus.ACTIVE,
                new_status=KeyStatus.EXHAUSTED,
                set_cooldown=False,
            )
            await self._cache.invalidate(user_id, provider.value)
        return True

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
        return await self.check_keys([key for key in keys if key.status != KeyStatus.DISABLED])

    async def check_keys(
        self,
        keys: Sequence[APIKey],
        *,
        concurrency: int = 1,
        delay_seconds: float = 0.0,
    ) -> list[APIKeyHealthCheckResult]:
        providers = {key.provider for key in keys}
        semaphores = {provider: asyncio.Semaphore(concurrency) for provider in providers}
        write_lock = asyncio.Lock()
        results: dict[int, APIKeyHealthCheckResult] = {}

        async def check_one(key: APIKey) -> None:
            async with semaphores[key.provider]:
                try:
                    probe_result = await self._probe_key(key)
                except Exception as exc:
                    logger.warning(
                        "health check skipped for key_id=%s: %s", key.id, type(exc).__name__
                    )
                    results[key.id] = APIKeyHealthCheckResult(
                        key_id=key.id, ok=False, detail="Health check could not be performed"
                    )
                    return
                if delay_seconds:
                    await asyncio.sleep(delay_seconds)

            async with write_lock:
                results[key.id] = await self._apply_health_result(key, probe_result)

        async with asyncio.TaskGroup() as group:
            for key in keys:
                group.create_task(check_one(key))

        return [results[key.id] for key in keys]

    @staticmethod
    async def _probe_key(key: APIKey) -> HealthCheckResult:
        provider = get_provider(key.provider.value)
        return await provider.health_check(decrypt_key(key.key_encrypted))

    async def _apply_health_result(
        self, key: APIKey, result: HealthCheckResult
    ) -> APIKeyHealthCheckResult:
        if result.latency_ms is not None:
            await self._repo.record_ping(key.id, key.user_id, result.latency_ms)

        if key.status != KeyStatus.DISABLED:
            if result.ok:
                if key.requests_today < key.daily_limit:
                    updated = await self._repo.compare_and_swap_status(
                        key.id,
                        user_id=key.user_id,
                        expected_status=key.status,
                        new_status=KeyStatus.ACTIVE,
                        cooldown_until=None,
                    )
                    if updated is not None:
                        await self._cache.invalidate(key.user_id, key.provider.value)
            elif key.status != KeyStatus.COOLDOWN:
                updated = await self._repo.compare_and_swap_status(
                    key.id,
                    user_id=key.user_id,
                    expected_status=key.status,
                    new_status=KeyStatus.EXHAUSTED,
                    set_cooldown=False,
                )
                if updated is not None:
                    await self._cache.invalidate(key.user_id, key.provider.value)

        return APIKeyHealthCheckResult(
            key_id=key.id, ok=result.ok, detail=result.detail, latency_ms=result.latency_ms
        )