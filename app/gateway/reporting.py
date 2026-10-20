import logging
from datetime import UTC, datetime

import httpx

from app.core.metrics import observe_attempt
from app.gateway.attempts import NO_USAGE, Attempt, TokenUsage, provider_label
from app.keys.enums import ProviderType
from app.monitoring.publisher import RequestEventPublisher
from app.monitoring.schemas import RequestEvent

logger = logging.getLogger(__name__)

NO_KEYS = "no_keys"
UPSTREAM_EXHAUSTED = "upstream_exhausted"


def extract_usage(response: httpx.Response) -> TokenUsage:
    try:
        body = response.json()
        if "usageMetadata" in body:
            return _from_gemini(body["usageMetadata"] or {})
        return _from_openai(body.get("usage") or {})
    except Exception:
        logger.warning("failed to parse usage data for token accounting", exc_info=True)
        return NO_USAGE


def _from_gemini(metadata: dict) -> TokenUsage:
    return TokenUsage(
        prompt=metadata.get("promptTokenCount"),
        completion=metadata.get("candidatesTokenCount"),
        total=metadata.get("totalTokenCount"),
    )


def _from_openai(usage: dict) -> TokenUsage:
    return TokenUsage(
        prompt=usage.get("prompt_tokens"),
        completion=usage.get("completion_tokens"),
        total=usage.get("total_tokens"),
    )


class AttemptReporter:
    def __init__(self, publisher: RequestEventPublisher | None = None) -> None:
        self._publisher = publisher

    async def report(self, attempt: Attempt, usage: TokenUsage = NO_USAGE) -> None:
        await self._dispatch(
            RequestEvent(
                user_id=attempt.user_id,
                request_id=attempt.request_id,
                attempt=attempt.number,
                timestamp=datetime.now(UTC),
                provider=attempt.provider_type.value,
                path=attempt.spec.path,
                method=attempt.spec.method,
                key_id=attempt.key.id,
                key_label=attempt.key.label,
                model=attempt.model,
                upstream_status=attempt.status_code,
                outcome=attempt.verdict.label,
                latency_ms=attempt.latency_ms,
                is_retry=attempt.is_retry,
                error_detail=attempt.error_detail,
                prompt_tokens=usage.prompt,
                completion_tokens=usage.completion,
                total_tokens=usage.total,
            )
        )

    async def report_pool_empty(
        self,
        *,
        user_id: int,
        request_id: str,
        number: int,
        provider_type: ProviderType | None,
        model: str | None,
        gave_up: bool,
    ) -> None:
        await self._dispatch(
            RequestEvent(
                user_id=user_id,
                request_id=request_id,
                attempt=number,
                timestamp=datetime.now(UTC),
                provider=provider_label(provider_type),
                path="",
                method="POST",
                model=model,
                outcome=UPSTREAM_EXHAUSTED if gave_up else NO_KEYS,
                is_retry=number > 1,
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
