import logging
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable

import httpx

from app.core.exceptions import NoAvailableKeysError, UpstreamExhaustedError
from app.keys.enums import ProviderType
from app.keys.service import KeyPoolService
from app.monitoring.publisher import RequestEventPublisher
from app.monitoring.schemas import RequestEvent
from app.providers.base import Provider
from app.providers.registry import get_provider

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class UpstreamRequestSpec:
    """Path/payload built for the specific provider a candidate key belongs to.

    Two different upstream providers speak different wire formats (e.g. Gemini
    needs the model baked into the URL and a translated body, while an
    OpenAI-compatible provider like OpenRouter can take the request mostly
    as-is). Because failover can hop between keys of different providers,
    this has to be (re)built for whichever key is actually being tried, not
    computed once up front for a single fixed provider.
    """

    path: str
    method: str
    payload: dict | None
    headers: dict


# Given the ProviderType of a candidate key, return the request spec to send to it.
RequestSpecBuilder = Callable[[ProviderType], UpstreamRequestSpec]


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
        """Send a request through the key pool, failing over across keys — and,
        when provider_type is None, across providers too — until one succeeds
        or every candidate has been tried.

        provider_type=None means "any provider the user has active keys for":
        the pool is searched across every provider, and each candidate key's
        own provider decides how build_request() translates the request for
        that specific attempt.
        """
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
            spec = build_request(key_provider_type)

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
            )
            return response

        provider_label = last_provider_type.value if last_provider_type is not None else "any"
        if last_response is not None:
            raise UpstreamExhaustedError(provider=provider_label, attempts=len(tried_key_ids))

        raise NoAvailableKeysError(provider=provider_label)