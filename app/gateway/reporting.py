from datetime import UTC, datetime

from app.core.metrics import observe_attempt
from app.gateway.attempts import NO_USAGE, AttemptContext, Outcome, TokenUsage, provider_label
from app.keys.enums import ProviderType
from app.monitoring.publisher import RequestEventPublisher
from app.monitoring.schemas import RequestEvent


class AttemptReporter:
    def __init__(self, publisher: RequestEventPublisher | None = None) -> None:
        self._publisher = publisher

    async def attempt(
        self,
        ctx: AttemptContext,
        outcome: Outcome,
        *,
        upstream_status: int | None,
        latency_ms: int | None,
        error_detail: str | None = None,
        usage: TokenUsage = NO_USAGE,
    ) -> None:
        await self._dispatch(
            RequestEvent(
                user_id=ctx.user_id,
                request_id=ctx.request_id,
                attempt=ctx.attempt,
                timestamp=datetime.now(UTC),
                provider=ctx.provider_type.value,
                path=ctx.spec.path,
                method=ctx.spec.method,
                key_id=ctx.key.id,
                key_label=ctx.key.label,
                model=ctx.effective_model,
                upstream_status=upstream_status,
                outcome=outcome.value,
                latency_ms=latency_ms,
                is_retry=ctx.is_retry,
                error_detail=error_detail,
                prompt_tokens=usage.prompt,
                completion_tokens=usage.completion,
                total_tokens=usage.total,
            )
        )

    async def pool_empty(
        self,
        *,
        user_id: int,
        request_id: str,
        attempt: int,
        provider_type: ProviderType | None,
        model: str | None,
        outcome: Outcome,
    ) -> None:
        await self._dispatch(
            RequestEvent(
                user_id=user_id,
                request_id=request_id,
                attempt=attempt,
                timestamp=datetime.now(UTC),
                provider=provider_label(provider_type),
                path="",
                method="POST",
                model=model,
                outcome=outcome.value,
                is_retry=attempt > 1,
            )
        )

    async def _dispatch(self, event: RequestEvent) -> None:
        observe_attempt(
            provider=event.provider,
            outcome=event.outcome,
            latency_ms=event.latency_ms,
            prompt_tokens=event.prompt_tokens,
            completion_tokens=event.completion_tokens,
        )
        if self._publisher is not None:
            await self._publisher.publish(event)
