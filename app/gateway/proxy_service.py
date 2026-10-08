import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from app.core.exceptions import NoAvailableKeysError, UpstreamExhaustedError
from app.core.metrics import observe_attempt
from app.core.request_context import get_request_id
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

_RETRY_OUTCOMES = frozenset({"invalid", "exhausted", "rate_limited", "upstream_error"})


@dataclass(frozen=True, slots=True)
class _AttemptContext:
    user_id: int
    request_id: str
    attempt: int
    dto: APIKeyDTO
    spec: UpstreamRequestSpec
    effective_model: str | None


async def _noop_recorder(
    prompt_tokens: int | None, completion_tokens: int | None, total_tokens: int | None
) -> None:
    return None


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
        observe_attempt(
            provider=provider_type.value if provider_type is not None else "any",
            outcome=outcome,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
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

    async def _emit_attempt(
        self,
        ctx: _AttemptContext,
        *,
        outcome: str,
        upstream_status: int | None,
        latency_ms: int | None,
        error_detail: str | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
    ) -> None:
        await self._emit(
            user_id=ctx.user_id,
            request_id=ctx.request_id,
            attempt=ctx.attempt,
            provider_type=ctx.dto.provider,
            path=ctx.spec.path,
            method=ctx.spec.method,
            key_id=ctx.dto.id,
            key_label=ctx.dto.label,
            upstream_status=upstream_status,
            outcome=outcome,
            latency_ms=latency_ms,
            error_detail=error_detail,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            model=ctx.effective_model,
        )

    async def _select_next_key(
        self,
        *,
        user_id: int,
        request_id: str,
        attempt: int,
        provider_type: ProviderType | None,
        model: str | None,
        tried_key_ids: set[int],
        last_provider_type: ProviderType | None,
    ) -> APIKeyDTO:
        dto = await self._key_pool.select_key(
            user_id, provider_type, model=model, exclude_ids=tried_key_ids
        )
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
        return dto

    async def _begin_attempt(
        self,
        *,
        user_id: int,
        request_id: str,
        attempt: int,
        provider_type: ProviderType | None,
        model: str | None,
        tried_key_ids: set[int],
        last_provider_type: ProviderType | None,
        build_request: RequestSpecBuilder,
    ) -> tuple[Provider, _AttemptContext]:
        dto = await self._select_next_key(
            user_id=user_id,
            request_id=request_id,
            attempt=attempt,
            provider_type=provider_type,
            model=model,
            tried_key_ids=tried_key_ids,
            last_provider_type=last_provider_type,
        )
        tried_key_ids.add(dto.id)
        ctx = _AttemptContext(
            user_id=user_id,
            request_id=request_id,
            attempt=attempt,
            dto=dto,
            spec=build_request(dto),
            effective_model=dto.model or model or self._default_models.get(dto.provider),
        )
        return get_provider(dto.provider.value), ctx

    async def _record_network_error(
        self, ctx: _AttemptContext, exc: httpx.HTTPError, latency_ms: int
    ) -> None:
        logger.warning(
            "attempt=%d key_id=%s provider=%s network error %s, retrying",
            ctx.attempt, ctx.dto.id, ctx.dto.provider.value, type(exc).__name__,
        )
        await self._emit_attempt(
            ctx,
            outcome="error",
            upstream_status=None,
            latency_ms=latency_ms,
            error_detail=type(exc).__name__,
        )

    async def _record_attempt_outcome(
        self,
        *,
        provider: Provider,
        response: httpx.Response,
        ctx: _AttemptContext,
        latency_ms: int,
    ) -> str:
        dto = ctx.dto
        key_provider_type = dto.provider

        if provider.is_key_invalid(response):
            await self._key_pool.record_invalid(dto.id, ctx.user_id, key_provider_type)
            await self._emit_attempt(
                ctx, outcome="invalid", upstream_status=response.status_code, latency_ms=latency_ms
            )
            logger.info("attempt=%d key_id=%s provider=%s invalid, retrying", ctx.attempt, dto.id, key_provider_type.value)
            return "invalid"

        if provider.is_key_exhausted(response):
            await self._key_pool.record_exhausted(dto.id, ctx.user_id, key_provider_type)
            await self._emit_attempt(
                ctx, outcome="exhausted", upstream_status=response.status_code, latency_ms=latency_ms
            )
            logger.info("attempt=%d key_id=%s provider=%s exhausted, retrying", ctx.attempt, dto.id, key_provider_type.value)
            return "exhausted"

        if provider.is_rate_limited(response):
            await self._key_pool.record_rate_limited(dto.id, ctx.user_id, key_provider_type)
            await self._emit_attempt(
                ctx, outcome="rate_limited", upstream_status=response.status_code, latency_ms=latency_ms
            )
            logger.info("attempt=%d key_id=%s provider=%s rate-limited, retrying", ctx.attempt, dto.id, key_provider_type.value)
            return "rate_limited"

        if response.status_code >= 500:
            await self._emit_attempt(
                ctx,
                outcome="error",
                upstream_status=response.status_code,
                latency_ms=latency_ms,
                error_detail=f"HTTP {response.status_code}",
            )
            logger.info(
                "attempt=%d key_id=%s provider=%s upstream status=%d, retrying",
                ctx.attempt, dto.id, key_provider_type.value, response.status_code,
            )
            return "upstream_error"

        if response.status_code >= 400:
            await self._emit_attempt(
                ctx,
                outcome="error",
                upstream_status=response.status_code,
                latency_ms=latency_ms,
                error_detail=f"HTTP {response.status_code}",
            )
            return "client_error"

        recorded = await self._key_pool.record_success(dto.id, ctx.user_id, key_provider_type)
        if not recorded:
            logger.warning(
                "key_id=%s provider=%s succeeded upstream but daily limit was already exhausted "
                "at the moment of recording (concurrent request likely used the last slot first)",
                dto.id, key_provider_type.value,
            )
        return "success"

    @staticmethod
    def _extract_usage(response: httpx.Response) -> tuple[int | None, int | None, int | None]:
        try:
            body = response.json()
            if "usageMetadata" in body:
                usage = body.get("usageMetadata") or {}
                return usage.get("promptTokenCount"), usage.get("candidatesTokenCount"), usage.get("totalTokenCount")
            usage = body.get("usage") or {}
            return usage.get("prompt_tokens"), usage.get("completion_tokens"), usage.get("total_tokens")
        except Exception:
            logger.warning("failed to parse usage data for token accounting", exc_info=True)
            return None, None, None

    def _exhausted_error(
        self, tried_key_ids: set[int], last_provider_type: ProviderType | None
    ) -> Exception:
        provider_label = last_provider_type.value if last_provider_type is not None else "any"
        if tried_key_ids:
            return UpstreamExhaustedError(provider=provider_label, attempts=len(tried_key_ids))
        return NoAvailableKeysError(provider=provider_label)

    async def proxy_request(
        self,
        *,
        user_id: int,
        build_request: RequestSpecBuilder,
        provider_type: ProviderType | None = None,
        model: str | None = None,
    ) -> tuple[httpx.Response, ProviderType]:
        request_id = get_request_id() or uuid.uuid4().hex
        tried_key_ids: set[int] = set()
        last_provider_type: ProviderType | None = provider_type

        for attempt in range(1, self._max_attempts + 1):
            provider, ctx = await self._begin_attempt(
                user_id=user_id,
                request_id=request_id,
                attempt=attempt,
                provider_type=provider_type,
                model=model,
                tried_key_ids=tried_key_ids,
                last_provider_type=last_provider_type,
                build_request=build_request,
            )
            dto, spec = ctx.dto, ctx.spec
            key_provider_type = dto.provider
            last_provider_type = key_provider_type

            started = time.monotonic()
            try:
                response = await provider.forward(
                    key=dto.decrypted_key,
                    path=spec.path,
                    method=spec.method,
                    payload=spec.payload,
                    headers=spec.headers,
                )
            except httpx.HTTPError as exc:
                await self._record_network_error(ctx, exc, int((time.monotonic() - started) * 1000))
                continue
            latency_ms = int((time.monotonic() - started) * 1000)

            outcome = await self._record_attempt_outcome(
                provider=provider, response=response, ctx=ctx, latency_ms=latency_ms
            )
            if outcome in _RETRY_OUTCOMES:
                continue
            if outcome == "client_error":
                return response, key_provider_type

            prompt_tokens, completion_tokens, total_tokens = self._extract_usage(response)
            await self._emit_attempt(
                ctx,
                outcome="success",
                upstream_status=response.status_code,
                latency_ms=latency_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            )
            return response, key_provider_type

        raise self._exhausted_error(tried_key_ids, last_provider_type)

    @asynccontextmanager
    async def proxy_stream_request(
        self,
        *,
        user_id: int,
        build_request: RequestSpecBuilder,
        provider_type: ProviderType | None = None,
        model: str | None = None,
    ) -> AsyncIterator[tuple[httpx.Response, TokenRecorder, ProviderType]]:
        request_id = get_request_id() or uuid.uuid4().hex
        tried_key_ids: set[int] = set()
        last_provider_type: ProviderType | None = provider_type

        for attempt in range(1, self._max_attempts + 1):
            provider, ctx = await self._begin_attempt(
                user_id=user_id,
                request_id=request_id,
                attempt=attempt,
                provider_type=provider_type,
                model=model,
                tried_key_ids=tried_key_ids,
                last_provider_type=last_provider_type,
                build_request=build_request,
            )
            dto, spec = ctx.dto, ctx.spec
            key_provider_type = dto.provider
            last_provider_type = key_provider_type

            started = time.monotonic()
            async with AsyncExitStack() as stack:
                try:
                    response = await stack.enter_async_context(
                        provider.forward_stream(
                            key=dto.decrypted_key,
                            path=spec.path,
                            method=spec.method,
                            payload=spec.payload,
                            headers=spec.headers,
                        )
                    )
                except httpx.HTTPError as exc:
                    await self._record_network_error(ctx, exc, int((time.monotonic() - started) * 1000))
                    continue
                latency_ms = int((time.monotonic() - started) * 1000)

                outcome = await self._record_attempt_outcome(
                    provider=provider, response=response, ctx=ctx, latency_ms=latency_ms
                )
                if outcome in _RETRY_OUTCOMES:
                    continue
                if outcome == "client_error":
                    yield response, _noop_recorder, key_provider_type
                    return

                async def record_tokens(
                    prompt_tokens: int | None,
                    completion_tokens: int | None,
                    total_tokens: int | None,
                    *,
                    _ctx: _AttemptContext = ctx,
                    _status_code: int = response.status_code,
                    _latency_ms: int = latency_ms,
                ) -> None:
                    await self._emit_attempt(
                        _ctx,
                        outcome="success",
                        upstream_status=_status_code,
                        latency_ms=_latency_ms,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=total_tokens,
                    )

                yield response, record_tokens, key_provider_type
                return

        raise self._exhausted_error(tried_key_ids, last_provider_type)
