import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, field

import httpx

from app.core.exceptions import LLMGatewayError, NoAvailableKeysError, UpstreamExhaustedError
from app.core.request_context import get_request_id
from app.gateway.attempts import (
    AttemptContext,
    Outcome,
    RequestSpecBuilder,
    TokenRecorder,
    TokenUsage,
    UpstreamRequestSpec,
    Verdict,
    classify_response,
    provider_label,
)
from app.gateway.reporting import AttemptReporter
from app.gateway.usage import extract_usage
from app.keys.enums import ProviderType
from app.keys.schemas import APIKeyDTO
from app.keys.service import KeyPoolService
from app.monitoring.publisher import RequestEventPublisher
from app.providers.base import parse_retry_after
from app.providers.registry import get_provider

__all__ = ["GatewayService", "RequestSpecBuilder", "TokenRecorder", "UpstreamRequestSpec"]

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _RequestState:
    user_id: int
    build_request: RequestSpecBuilder
    provider_type: ProviderType | None
    model: str | None
    request_id: str = field(default_factory=lambda: get_request_id() or uuid.uuid4().hex)
    tried_key_ids: set[int] = field(default_factory=set)
    last_provider_type: ProviderType | None = field(init=False)

    def __post_init__(self) -> None:
        self.last_provider_type = self.provider_type


@dataclass(frozen=True, slots=True)
class _Upstream:
    response: httpx.Response
    ctx: AttemptContext
    verdict: Verdict
    latency_ms: int


async def _noop_recorder(
    prompt_tokens: int | None, completion_tokens: int | None, total_tokens: int | None
) -> None:
    return None


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


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
        self._reporter = AttemptReporter(event_publisher)
        self._default_models = default_models or {}


    async def proxy_request(
        self,
        *,
        user_id: int,
        build_request: RequestSpecBuilder,
        provider_type: ProviderType | None = None,
        model: str | None = None,
    ) -> tuple[httpx.Response, ProviderType]:
        state = _RequestState(user_id, build_request, provider_type, model)
        async with self._open_upstream(state, stream=False) as upstream:
            if upstream.verdict is Verdict.SUCCESS:
                await self._report_success(upstream, extract_usage(upstream.response))
            return upstream.response, upstream.ctx.provider_type

    @asynccontextmanager
    async def proxy_stream_request(
        self,
        *,
        user_id: int,
        build_request: RequestSpecBuilder,
        provider_type: ProviderType | None = None,
        model: str | None = None,
    ) -> AsyncIterator[tuple[httpx.Response, TokenRecorder, ProviderType]]:
        state = _RequestState(user_id, build_request, provider_type, model)
        async with self._open_upstream(state, stream=True) as upstream:
            yield upstream.response, self._token_recorder(upstream), upstream.ctx.provider_type


    @asynccontextmanager
    async def _open_upstream(
        self, state: _RequestState, *, stream: bool
    ) -> AsyncIterator[_Upstream]:
        for attempt in range(1, self._max_attempts + 1):
            ctx = await self._begin_attempt(state, attempt)
            started = time.monotonic()

            async with AsyncExitStack() as stack:
                try:
                    response = await stack.enter_async_context(_send(ctx, stream=stream))
                except httpx.HTTPError as exc:
                    await self._record_network_error(ctx, exc, _elapsed_ms(started))
                    continue
                latency_ms = _elapsed_ms(started)

                verdict = await self._settle(ctx, response, latency_ms)
                if verdict.retryable:
                    continue

                yield _Upstream(response, ctx, verdict, latency_ms)
                return

        raise self._attempts_used_up_error(state)

    async def _begin_attempt(self, state: _RequestState, attempt: int) -> AttemptContext:
        key = await self._select_key(state, attempt)
        state.tried_key_ids.add(key.id)
        state.last_provider_type = key.provider
        return AttemptContext(
            user_id=state.user_id,
            request_id=state.request_id,
            attempt=attempt,
            key=key,
            provider=get_provider(key.provider.value),
            spec=state.build_request(key),
            effective_model=key.model or state.model or self._default_models.get(key.provider),
        )

    async def _select_key(self, state: _RequestState, attempt: int) -> APIKeyDTO:
        key = await self._key_pool.select_key(
            state.user_id,
            state.provider_type,
            model=state.model,
            exclude_ids=state.tried_key_ids,
        )
        if key is not None:
            return key

        gave_up_after_trying = bool(state.tried_key_ids)
        await self._reporter.pool_empty(
            user_id=state.user_id,
            request_id=state.request_id,
            attempt=attempt,
            provider_type=state.last_provider_type,
            model=state.model,
            outcome=Outcome.UPSTREAM_EXHAUSTED if gave_up_after_trying else Outcome.NO_KEYS,
        )
        if gave_up_after_trying:
            raise UpstreamExhaustedError(
                provider=provider_label(state.provider_type), attempts=len(state.tried_key_ids)
            )
        raise NoAvailableKeysError(provider=_scope(state.provider_type, state.model))

    @staticmethod
    def _attempts_used_up_error(state: _RequestState) -> LLMGatewayError:
        label = provider_label(state.last_provider_type)
        if state.tried_key_ids:
            return UpstreamExhaustedError(provider=label, attempts=len(state.tried_key_ids))
        return NoAvailableKeysError(provider=label)


    async def _settle(
        self, ctx: AttemptContext, response: httpx.Response, latency_ms: int
    ) -> Verdict:
        verdict = classify_response(ctx.provider, response)

        await self._update_key_pool(ctx, response, verdict)

        if verdict is not Verdict.SUCCESS:
            await self._reporter.attempt(
                ctx,
                verdict.outcome,
                upstream_status=response.status_code,
                latency_ms=latency_ms,
                error_detail=_error_detail(verdict, response),
            )
        if verdict.retryable:
            logger.info(
                "attempt=%d key_id=%s provider=%s %s, retrying",
                ctx.attempt,
                ctx.key.id,
                ctx.provider_type.value,
                _retry_reason(verdict, response),
            )
        return verdict

    async def _update_key_pool(
        self, ctx: AttemptContext, response: httpx.Response, verdict: Verdict
    ) -> None:
        key_id, user_id, provider = ctx.key.id, ctx.user_id, ctx.provider_type
        match verdict:
            case Verdict.KEY_INVALID:
                await self._key_pool.record_invalid(key_id, user_id, provider)
            case Verdict.KEY_EXHAUSTED:
                await self._key_pool.record_exhausted(key_id, user_id, provider)
            case Verdict.RATE_LIMITED:
                await self._key_pool.record_rate_limited(
                    key_id, user_id, provider, retry_after_seconds=parse_retry_after(response)
                )
            case Verdict.SUCCESS:
                if not await self._key_pool.record_success(key_id, user_id, provider):
                    logger.warning(
                        "key_id=%s provider=%s succeeded upstream but daily limit was already "
                        "exhausted at the moment of recording (concurrent request likely used "
                        "the last slot first)",
                        key_id,
                        provider.value,
                    )

    async def _record_network_error(
        self, ctx: AttemptContext, exc: httpx.HTTPError, latency_ms: int
    ) -> None:
        logger.warning(
            "attempt=%d key_id=%s provider=%s network error %s, retrying",
            ctx.attempt,
            ctx.key.id,
            ctx.provider_type.value,
            type(exc).__name__,
        )
        await self._reporter.attempt(
            ctx,
            Outcome.ERROR,
            upstream_status=None,
            latency_ms=latency_ms,
            error_detail=type(exc).__name__,
        )


    def _token_recorder(self, upstream: _Upstream) -> TokenRecorder:
        if upstream.verdict is not Verdict.SUCCESS:
            return _noop_recorder

        async def record_tokens(
            prompt_tokens: int | None, completion_tokens: int | None, total_tokens: int | None
        ) -> None:
            usage = TokenUsage(prompt_tokens, completion_tokens, total_tokens)
            await self._report_success(upstream, usage)

        return record_tokens

    async def _report_success(self, upstream: _Upstream, usage: TokenUsage) -> None:
        await self._reporter.attempt(
            upstream.ctx,
            Outcome.SUCCESS,
            upstream_status=upstream.response.status_code,
            latency_ms=upstream.latency_ms,
            usage=usage,
        )


@asynccontextmanager
async def _send(ctx: AttemptContext, *, stream: bool) -> AsyncIterator[httpx.Response]:
    request = {
        "key": ctx.key.decrypted_key,
        "path": ctx.spec.path,
        "method": ctx.spec.method,
        "payload": ctx.spec.payload,
        "headers": ctx.spec.headers,
    }
    if stream:
        async with ctx.provider.forward_stream(**request) as response:
            yield response
    else:
        yield await ctx.provider.forward(**request)


def _scope(provider_type: ProviderType | None, model: str | None) -> str:
    label = provider_label(provider_type)
    return f"{label}' for model '{model}" if model else label


def _error_detail(verdict: Verdict, response: httpx.Response) -> str | None:
    if verdict in (Verdict.SERVER_ERROR, Verdict.CLIENT_ERROR):
        return f"HTTP {response.status_code}"
    return None


def _retry_reason(verdict: Verdict, response: httpx.Response) -> str:
    match verdict:
        case Verdict.KEY_INVALID:
            return "invalid"
        case Verdict.KEY_EXHAUSTED:
            return "exhausted"
        case Verdict.RATE_LIMITED:
            return "rate-limited"
        case _:
            return f"upstream status={response.status_code}"
