import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, field

import httpx

from app.core.exceptions import LLMGatewayError, NoAvailableKeysError, UpstreamExhaustedError
from app.core.request_context import get_request_id
from app.gateway.attempts import (
    Attempt,
    RequestSpecBuilder,
    TokenRecorder,
    TokenUsage,
    UpstreamRequestSpec,
    Verdict,
    classify_response,
    provider_label,
)
from app.gateway.reporting import AttemptReporter, extract_usage
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
        async with self._open_upstream(state, stream=False) as attempt:
            if attempt.verdict is Verdict.SUCCESS:
                await self._reporter.report(attempt, extract_usage(attempt.response))
            return attempt.response, attempt.provider_type

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
        async with self._open_upstream(state, stream=True) as attempt:
            yield attempt.response, self._token_recorder(attempt), attempt.provider_type

    @asynccontextmanager
    async def _open_upstream(self, state: _RequestState, *, stream: bool) -> AsyncIterator[Attempt]:
        for number in range(1, self._max_attempts + 1):
            attempt = await self._begin_attempt(state, number)

            async with AsyncExitStack() as stack:
                try:
                    response = await stack.enter_async_context(_send(attempt, stream=stream))
                except httpx.HTTPError as exc:
                    attempt.finish(Verdict.NETWORK_ERROR, error=exc)
                else:
                    verdict = classify_response(attempt.provider, response)
                    attempt.finish(verdict, response=response)

                await self._settle(attempt)
                if attempt.verdict.retryable:
                    continue

                yield attempt
                return

        raise self._attempts_used_up_error(state)

    async def _begin_attempt(self, state: _RequestState, number: int) -> Attempt:
        key = await self._select_key(state, number)
        state.tried_key_ids.add(key.id)
        state.last_provider_type = key.provider
        return Attempt(
            user_id=state.user_id,
            request_id=state.request_id,
            number=number,
            key=key,
            provider=get_provider(key.provider.value),
            spec=state.build_request(key),
            model=key.model or state.model or self._default_models.get(key.provider),
        )

    async def _select_key(self, state: _RequestState, number: int) -> APIKeyDTO:
        key = await self._key_pool.select_key(
            state.user_id,
            state.provider_type,
            model=state.model,
            exclude_ids=state.tried_key_ids,
        )
        if key is not None:
            return key

        gave_up = bool(state.tried_key_ids)
        await self._reporter.report_pool_empty(
            user_id=state.user_id,
            request_id=state.request_id,
            number=number,
            provider_type=state.last_provider_type,
            model=state.model,
            gave_up=gave_up,
        )
        if gave_up:
            raise UpstreamExhaustedError(
                provider=provider_label(state.provider_type), attempts=len(state.tried_key_ids)
            )
        label = provider_label(state.provider_type)
        scope = f"{label}' for model '{state.model}" if state.model else label
        raise NoAvailableKeysError(provider=scope)

    @staticmethod
    def _attempts_used_up_error(state: _RequestState) -> LLMGatewayError:
        label = provider_label(state.last_provider_type)
        if state.tried_key_ids:
            return UpstreamExhaustedError(provider=label, attempts=len(state.tried_key_ids))
        return NoAvailableKeysError(provider=label)

    async def _settle(self, attempt: Attempt) -> None:
        await self._update_key_pool(attempt)

        if attempt.verdict is not Verdict.SUCCESS:
            await self._reporter.report(attempt)

        if attempt.verdict.retryable:
            reason = attempt.verdict.description
            if attempt.error_detail:
                reason = f"{reason} ({attempt.error_detail})"
            level = logging.WARNING if attempt.verdict is Verdict.NETWORK_ERROR else logging.INFO
            logger.log(
                level,
                "attempt=%d key_id=%s provider=%s %s, retrying",
                attempt.number,
                attempt.key.id,
                attempt.provider_type.value,
                reason,
            )

    async def _update_key_pool(self, attempt: Attempt) -> None:
        key_id, user_id, provider = attempt.key.id, attempt.user_id, attempt.provider_type
        match attempt.verdict:
            case Verdict.KEY_INVALID:
                await self._key_pool.record_invalid(key_id, user_id, provider)
            case Verdict.KEY_EXHAUSTED:
                await self._key_pool.record_exhausted(key_id, user_id, provider)
            case Verdict.RATE_LIMITED:
                await self._key_pool.record_rate_limited(
                    key_id,
                    user_id,
                    provider,
                    retry_after_seconds=parse_retry_after(attempt.response),
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

    def _token_recorder(self, attempt: Attempt) -> TokenRecorder:
        if attempt.verdict is not Verdict.SUCCESS:
            return _noop_recorder

        async def record_tokens(
            prompt_tokens: int | None, completion_tokens: int | None, total_tokens: int | None
        ) -> None:
            usage = TokenUsage(prompt_tokens, completion_tokens, total_tokens)
            await self._reporter.report(attempt, usage)

        return record_tokens


@asynccontextmanager
async def _send(attempt: Attempt, *, stream: bool) -> AsyncIterator[httpx.Response]:
    request = {
        "key": attempt.key.decrypted_key,
        "path": attempt.spec.path,
        "method": attempt.spec.method,
        "payload": attempt.spec.payload,
        "headers": attempt.spec.headers,
    }
    if stream:
        async with attempt.provider.forward_stream(**request) as response:
            yield response
    else:
        yield await attempt.provider.forward(**request)
