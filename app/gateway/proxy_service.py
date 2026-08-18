import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from app.core.exceptions import NoAvailableKeysError, UpstreamExhaustedError
from app.keys.enums import ProviderType
from app.keys.schemas import APIKeyDTO
from app.keys.service import KeyPoolService
from app.monitoring.publisher import RequestEventPublisher
from app.monitoring.schemas import RequestEvent
from app.providers.base import Provider
from app.providers.registry import get_provider

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class UpstreamRequestSpec:
    path: str
    method: str
    payload: dict | None
    headers: dict

RequestSpecBuilder = Callable[[APIKeyDTO], UpstreamRequestSpec]

TokenRecorder = Callable[[int | None, int | None, int | None], Awaitable[None]]


class GatewayService:
    def __init__(
        self,
        key_pool: KeyPoolService,
        max_attempts: int,
        event_publisher: RequestEventPublisher | None = None,
        default_models: dict[ProviderType, str] | None = None,
    ) -> None:
        self._key_pool = key_pool
        self._max_attempts = max_attempts
        self._events = event_publisher
        self._default_models = default_models or {}

    async def _emit(
        self,
        *,
        user_id: int,
        request_id: str,
        attempt: int,
        provider_type: ProviderType | None,
        path: str | None,
        method: str,
        key_id: int | None,
        key_label: str | None,
        upstream_status: int | None,
        outcome: str,
        latency_ms: int | None,
        error_detail: str | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
        model: str | None = None,
    ) -> None:
        if self._events is None:
            return
        await self._events.publish(
            RequestEvent(
                user_id=user_id,
                request_id=request_id,
                attempt=attempt,
                timestamp=datetime.now(UTC),
                provider=provider_type.value if provider_type is not None else "any",
                path=path or "",
                method=method,
                key_id=key_id,
                key_label=key_label,
                model=model,
                upstream_status=upstream_status,
                outcome=outcome,
                latency_ms=latency_ms,
                is_retry=attempt > 1,
                error_detail=error_detail,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            )
        )

    async def proxy_request(
        self,
        *,
        user_id: int,
        build_request: RequestSpecBuilder,
        provider_type: ProviderType | None = None,
        model: str | None = None,
    ) -> httpx.Response:
        request_id = uuid.uuid4().hex
        tried_key_ids: set[int] = set()
        last_response: httpx.Response | None = None
        last_provider_type: ProviderType | None = provider_type

        for attempt in range(1, self._max_attempts + 1):
            dto = await self._key_pool.select_key(user_id, provider_type, model=model)
            if dto is None:
                outcome = "upstream_exhausted" if tried_key_ids else "no_keys"
                await self._emit(
                    user_id=user_id,
                    request_id=request_id,
                    attempt=attempt,
                    provider_type=last_provider_type,
                    path=None,
                    method="POST",
                    key_id=None,
                    key_label=None,
                    upstream_status=None,
                    outcome=outcome,
                    latency_ms=None,
                    model=model,
                )
                provider_label = provider_type.value if provider_type is not None else "any"
                if tried_key_ids:
                    raise UpstreamExhaustedError(provider=provider_label, attempts=len(tried_key_ids))
                if model:
                    provider_label = f"{provider_label}' for model '{model}"
                raise NoAvailableKeysError(provider=provider_label)

            if dto.id in tried_key_ids:
                break
            tried_key_ids.add(dto.id)

            key_provider_type = dto.provider
            last_provider_type = key_provider_type
            provider: Provider = get_provider(key_provider_type.value)
            spec = build_request(dto)
            effective_model = dto.model or model or self._default_models.get(key_provider_type)

            started = time.monotonic()
            response = await provider.forward(
                key=dto.decrypted_key,
                path=spec.path,
                method=spec.method,
                payload=spec.payload,
                headers=spec.headers,
            )
            latency_ms = int((time.monotonic() - started) * 1000)
            last_response = response

            if provider.is_key_exhausted(response):
                await self._key_pool.record_exhausted(dto.id, user_id, key_provider_type)
                await self._emit(
                    user_id=user_id,
                    request_id=request_id,
                    attempt=attempt,
                    provider_type=key_provider_type,
                    path=spec.path,
                    method=spec.method,
                    key_id=dto.id,
                    key_label=dto.label,
                    upstream_status=response.status_code,
                    outcome="exhausted",
                    latency_ms=latency_ms,
                    model=effective_model,
                )
                logger.info("attempt=%d key_id=%s provider=%s exhausted, retrying", attempt, dto.id, key_provider_type.value)
                continue

            if provider.is_rate_limited(response):
                await self._key_pool.record_rate_limited(dto.id, user_id, key_provider_type)
                await self._emit(
                    user_id=user_id,
                    request_id=request_id,
                    attempt=attempt,
                    provider_type=key_provider_type,
                    path=spec.path,
                    method=spec.method,
                    key_id=dto.id,
                    key_label=dto.label,
                    upstream_status=response.status_code,
                    outcome="rate_limited",
                    latency_ms=latency_ms,
                    model=effective_model,
                )
                logger.info("attempt=%d key_id=%s provider=%s rate-limited, retrying", attempt, dto.id, key_provider_type.value)
                continue

            await self._key_pool.record_success(dto.id, user_id, key_provider_type)
            prompt_tokens = completion_tokens = total_tokens = None
            try:
                body = response.json()
                if "usageMetadata" in body:
                    usage = body.get("usageMetadata") or {}
                    prompt_tokens = usage.get("promptTokenCount")
                    completion_tokens = usage.get("candidatesTokenCount")
                    total_tokens = usage.get("totalTokenCount")
                else:
                    usage = body.get("usage") or {}
                    prompt_tokens = usage.get("prompt_tokens")
                    completion_tokens = usage.get("completion_tokens")
                    total_tokens = usage.get("total_tokens")
            except Exception:
                logger.warning("failed to parse usage data for token accounting", exc_info=True)
            await self._emit(
                user_id=user_id,
                request_id=request_id,
                attempt=attempt,
                provider_type=key_provider_type,
                path=spec.path,
                method=spec.method,
                key_id=dto.id,
                key_label=dto.label,
                upstream_status=response.status_code,
                outcome="success",
                latency_ms=latency_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                model=effective_model,
            )
            return response

        provider_label = last_provider_type.value if last_provider_type is not None else "any"
        if last_response is not None:
            raise UpstreamExhaustedError(provider=provider_label, attempts=len(tried_key_ids))

        raise NoAvailableKeysError(provider=provider_label)

    @asynccontextmanager
    async def proxy_stream_request(
        self,
        *,
        user_id: int,
        build_request: RequestSpecBuilder,
        provider_type: ProviderType | None = None,
        model: str | None = None,
    ) -> AsyncIterator[tuple[httpx.Response, TokenRecorder]]:
        request_id = uuid.uuid4().hex
        tried_key_ids: set[int] = set()
        last_status: int | None = None
        last_provider_type: ProviderType | None = provider_type

        for attempt in range(1, self._max_attempts + 1):
            dto = await self._key_pool.select_key(user_id, provider_type, model=model)
            if dto is None:
                outcome = "upstream_exhausted" if tried_key_ids else "no_keys"
                await self._emit(
                    user_id=user_id,
                    request_id=request_id,
                    attempt=attempt,
                    provider_type=last_provider_type,
                    path=None,
                    method="POST",
                    key_id=None,
                    key_label=None,
                    upstream_status=None,
                    outcome=outcome,
                    latency_ms=None,
                    model=model,
                )
                provider_label = provider_type.value if provider_type is not None else "any"
                if tried_key_ids:
                    raise UpstreamExhaustedError(provider=provider_label, attempts=len(tried_key_ids))
                if model:
                    provider_label = f"{provider_label}' for model '{model}"
                raise NoAvailableKeysError(provider=provider_label)

            if dto.id in tried_key_ids:
                break
            tried_key_ids.add(dto.id)

            key_provider_type = dto.provider
            last_provider_type = key_provider_type
            provider: Provider = get_provider(key_provider_type.value)
            spec = build_request(dto)
            effective_model = dto.model or model or self._default_models.get(key_provider_type)

            started = time.monotonic()
            async with provider.forward_stream(
                key=dto.decrypted_key,
                path=spec.path,
                method=spec.method,
                payload=spec.payload,
                headers=spec.headers,
            ) as response:
                latency_ms = int((time.monotonic() - started) * 1000)
                last_status = response.status_code

                if provider.is_key_exhausted(response):
                    await self._key_pool.record_exhausted(dto.id, user_id, key_provider_type)
                    await self._emit(
                        user_id=user_id,
                        request_id=request_id,
                        attempt=attempt,
                        provider_type=key_provider_type,
                        path=spec.path,
                        method=spec.method,
                        key_id=dto.id,
                        key_label=dto.label,
                        upstream_status=response.status_code,
                        outcome="exhausted",
                        latency_ms=latency_ms,
                        model=effective_model,
                    )
                    logger.info(
                        "attempt=%d key_id=%s provider=%s exhausted (stream), retrying",
                        attempt, dto.id, key_provider_type.value,
                    )
                    continue

                if provider.is_rate_limited(response):
                    await self._key_pool.record_rate_limited(dto.id, user_id, key_provider_type)
                    await self._emit(
                        user_id=user_id,
                        request_id=request_id,
                        attempt=attempt,
                        provider_type=key_provider_type,
                        path=spec.path,
                        method=spec.method,
                        key_id=dto.id,
                        key_label=dto.label,
                        upstream_status=response.status_code,
                        outcome="rate_limited",
                        latency_ms=latency_ms,
                        model=effective_model,
                    )
                    logger.info(
                        "attempt=%d key_id=%s provider=%s rate-limited (stream), retrying",
                        attempt, dto.id, key_provider_type.value,
                    )
                    continue

                await self._key_pool.record_success(dto.id, user_id, key_provider_type)

                async def record_tokens(
                    prompt_tokens: int | None,
                    completion_tokens: int | None,
                    total_tokens: int | None,
                    *,
                    _attempt: int = attempt,
                    _key_provider_type: ProviderType = key_provider_type,
                    _spec: UpstreamRequestSpec = spec,
                    _dto: APIKeyDTO = dto,
                    _status_code: int = response.status_code,
                    _latency_ms: int = latency_ms,
                    _model: str | None = effective_model,
                ) -> None:
                    await self._emit(
                        user_id=user_id,
                        request_id=request_id,
                        attempt=_attempt,
                        provider_type=_key_provider_type,
                        path=_spec.path,
                        method=_spec.method,
                        key_id=_dto.id,
                        key_label=_dto.label,
                        upstream_status=_status_code,
                        outcome="success",
                        latency_ms=_latency_ms,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=total_tokens,
                        model=_model,
                    )

                yield response, record_tokens
                return

        provider_label = last_provider_type.value if last_provider_type is not None else "any"
        if last_status is not None:
            raise UpstreamExhaustedError(provider=provider_label, attempts=len(tried_key_ids))

        raise NoAvailableKeysError(provider=provider_label)