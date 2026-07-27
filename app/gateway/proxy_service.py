import logging
import time
import uuid
from datetime import UTC, datetime

import httpx

from app.core.exceptions import NoAvailableKeysError, UpstreamExhaustedError
from app.keys.enums import ProviderType
from app.keys.service import KeyPoolService
from app.monitoring.publisher import RequestEventPublisher
from app.monitoring.schemas import RequestEvent
from app.providers.base import Provider

logger = logging.getLogger(__name__)


class GatewayService:
    def __init__(
        self,
        key_pool: KeyPoolService,
        max_attempts: int,
        event_publisher: RequestEventPublisher | None = None,
    ) -> None:
        self._key_pool = key_pool
        self._max_attempts = max_attempts
        self._events = event_publisher

    async def _emit(
        self,
        *,
        user_id: int,
        request_id: str,
        attempt: int,
        provider_type: ProviderType,
        path: str,
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
    ) -> None:
        if self._events is None:
            return
        await self._events.publish(
            RequestEvent(
                user_id=user_id,
                request_id=request_id,
                attempt=attempt,
                timestamp=datetime.now(UTC),
                provider=provider_type.value,
                path=path,
                method=method,
                key_id=key_id,
                key_label=key_label,
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
        provider: Provider,
        provider_type: ProviderType,
        path: str,
        method: str,
        payload: dict | None,
        headers: dict,
        model: str | None = None,
    ) -> httpx.Response:
        request_id = uuid.uuid4().hex
        tried_key_ids: set[int] = set()
        last_response: httpx.Response | None = None

        for attempt in range(1, self._max_attempts + 1):
            dto = await self._key_pool.select_key(user_id, provider_type, model=model)
            if dto is None:
                outcome = "upstream_exhausted" if tried_key_ids else "no_keys"
                await self._emit(
                    user_id=user_id,
                    request_id=request_id,
                    attempt=attempt,
                    provider_type=provider_type,
                    path=path,
                    method=method,
                    key_id=None,
                    key_label=None,
                    upstream_status=None,
                    outcome=outcome,
                    latency_ms=None,
                )
                if tried_key_ids:
                    raise UpstreamExhaustedError(provider=provider_type.value, attempts=len(tried_key_ids))
                provider_label = f"{provider_type.value}' for model '{model}" if model else provider_type.value
                raise NoAvailableKeysError(provider=provider_label)

            if dto.id in tried_key_ids:
                break
            tried_key_ids.add(dto.id)

            started = time.monotonic()
            response = await provider.forward(
                key=dto.decrypted_key, 
                path=path,
                method=method,
                payload=payload,
                headers=headers,
            )
            latency_ms = int((time.monotonic() - started) * 1000)
            last_response = response

            if provider.is_key_exhausted(response):
                await self._key_pool.record_exhausted(dto.id, user_id, provider_type)
                await self._emit(
                    user_id=user_id,
                    request_id=request_id,
                    attempt=attempt,
                    provider_type=provider_type,
                    path=path,
                    method=method,
                    key_id=dto.id,
                    key_label=dto.label,
                    upstream_status=response.status_code,
                    outcome="exhausted",
                    latency_ms=latency_ms,
                )
                logger.info("attempt=%d key_id=%s exhausted, retrying", attempt, dto.id)
                continue

            if provider.is_rate_limited(response):
                await self._key_pool.record_rate_limited(dto.id, user_id, provider_type)
                await self._emit(
                    user_id=user_id,
                    request_id=request_id,
                    attempt=attempt,
                    provider_type=provider_type,
                    path=path,
                    method=method,
                    key_id=dto.id,
                    key_label=dto.label,
                    upstream_status=response.status_code,
                    outcome="rate_limited",
                    latency_ms=latency_ms,
                )
                logger.info("attempt=%d key_id=%s rate-limited, retrying", attempt, dto.id)
                continue

            await self._key_pool.record_success(dto.id, user_id, provider_type)
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
                provider_type=provider_type,
                path=path,
                method=method,
                key_id=dto.id,
                key_label=dto.label,
                upstream_status=response.status_code,
                outcome="success",
                latency_ms=latency_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            )
            return response

        if last_response is not None:
            raise UpstreamExhaustedError(provider=provider_type.value, attempts=len(tried_key_ids))

        raise NoAvailableKeysError(provider=provider_type.value)
