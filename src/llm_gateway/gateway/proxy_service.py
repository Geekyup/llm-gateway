import logging

import httpx

from llm_gateway.core.exceptions import NoAvailableKeysError, UpstreamExhaustedError
from llm_gateway.keys.enums import ProviderType
from llm_gateway.keys.service import KeyPoolService
from llm_gateway.providers.base import Provider

logger = logging.getLogger(__name__)


class GatewayService:
    """Orchestrates: pick a key -> call upstream -> on 429 mark cooldown and
    retry with a different key -> give up after N attempts.

    This is the only place that knows the failover *policy*; KeyPoolService
    only knows how to select/mark keys, Provider only knows how to talk to
    one upstream API.
    """

    def __init__(self, key_pool: KeyPoolService, max_attempts: int) -> None:
        self._key_pool = key_pool
        self._max_attempts = max_attempts

    async def proxy_request(
        self,
        *,
        provider: Provider,
        provider_type: ProviderType,
        path: str,
        method: str,
        payload: dict | None,
        headers: dict,
    ) -> httpx.Response:
        tried_key_ids: set[int] = set()
        last_response: httpx.Response | None = None

        for attempt in range(1, self._max_attempts + 1):
            dto = await self._key_pool.select_key(provider_type)
            if dto is None:
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

            response = await provider.forward(
                key=dto.decrypted_key,  # type: ignore[arg-type]  # always set by select_key
                path=path,
                method=method,
                payload=payload,
                headers=headers,
            )
            last_response = response

            if provider.is_key_exhausted(response):
                await self._key_pool.record_exhausted(dto.id, provider_type)
                logger.info("attempt=%d key_id=%s exhausted, retrying", attempt, dto.id)
                continue

            if provider.is_rate_limited(response):
                await self._key_pool.record_rate_limited(dto.id, provider_type)
                logger.info("attempt=%d key_id=%s rate-limited, retrying", attempt, dto.id)
                continue

            await self._key_pool.record_success(dto.id, provider_type)
            return response

        if last_response is not None:
            # Every attempt came back 429/403 — surface the last upstream
            # response's status/body rather than inventing a generic 503,
            # so the client sees exactly what Gemini said.
            raise UpstreamExhaustedError(provider_type.value, len(tried_key_ids))

        raise NoAvailableKeysError(provider_type.value)
