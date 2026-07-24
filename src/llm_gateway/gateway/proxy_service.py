import logging
import time
import uuid
from datetime import datetime, timezone

import httpx

from llm_gateway.core.exceptions import NoAvailableKeysError, UpstreamExhaustedError
from llm_gateway.keys.enums import ProviderType
from llm_gateway.keys.service import KeyPoolService
from llm_gateway.monitoring.publisher import RequestEventPublisher
from llm_gateway.monitoring.schemas import RequestEvent
from llm_gateway.providers.base import Provider

logger = logging.getLogger(__name__)


class GatewayService:
    """Orchestrates: pick a key -> call upstream -> on 429 mark cooldown and
    retry with a different key -> give up after N attempts.

    This is the only place that knows the failover *policy*; KeyPoolService
    only knows how to select/mark keys, Provider only knows how to talk to
    one upstream API.
    """

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
    ) -> None:
        if self._events is None:
            return
        await self._events.publish(
            RequestEvent(
                user_id=user_id,
                request_id=request_id,
                attempt=attempt,
                timestamp=datetime.now(timezone.utc),
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
    ) -> httpx.Response:
        request_id = uuid.uuid4().hex
        tried_key_ids: set[int] = set()
        last_response: httpx.Response | None = None

        for attempt in range(1, self._max_attempts + 1):
            dto = await self._key_pool.select_key(user_id, provider_type)
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
                    # We had candidates earlier but exhausted them all this request.
                    raise UpstreamExhaustedError(provider_type.value, len(tried_key_ids))
                raise NoAvailableKeysError(provider_type.value)

            if dto.id in tried_key_ids:
                # Round-robin cursor looped back before we hit max_attempts
                # because the pool is smaller than max_attempts — stop here
                # rather than hammering the same key again.
                break
            tried_key_ids.add(dto.id)

            started = time.monotonic()
            response = await provider.forward(
                key=dto.decrypted_key,  # type: ignore[arg-type]  # always set by select_key
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
            )
            return response

        if last_response is not None:
            # Every attempt came back 429/403 — surface the last upstream
            # response's status/body rather than inventing a generic 503,
            # so the client sees exactly what Gemini said.
            raise UpstreamExhaustedError(provider_type.value, len(tried_key_ids))

        raise NoAvailableKeysError(provider_type.value)
