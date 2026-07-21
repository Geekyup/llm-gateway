import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from llm_gateway.api.deps import get_gateway_service
from llm_gateway.core.exceptions import NoAvailableKeysError, ProviderNotSupportedError, UpstreamExhaustedError
from llm_gateway.gateway.dependencies import require_gateway_token
from llm_gateway.gateway.proxy_service import GatewayService
from llm_gateway.keys.enums import ProviderType
from llm_gateway.openai_compat.schemas import ChatCompletionRequest, OpenAIErrorDetail, OpenAIErrorResponse
from llm_gateway.openai_compat.translation import (
    gemini_path_for_model,
    gemini_response_to_openai,
    openai_request_to_gemini_payload,
)
from llm_gateway.providers.registry import get_provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["openai-compat"], dependencies=[Depends(require_gateway_token)])

# Every request through this endpoint goes to Gemini today. Once a second
# provider is registered, pick it from `request.model` (e.g. a prefix or
# an explicit mapping) instead of hardcoding this.
_PROVIDER_TYPE = ProviderType.GEMINI


def _openai_error(status_code: int, message: str, error_type: str) -> JSONResponse:
    body = OpenAIErrorResponse(error=OpenAIErrorDetail(message=message, type=error_type))
    return JSONResponse(status_code=status_code, content=body.model_dump())


@router.post("/chat/completions", operation_id="openai_chat_completions")
async def chat_completions(
    request: ChatCompletionRequest,
    gateway: GatewayService = Depends(get_gateway_service),
):
    """OpenAI-compatible chat completions, backed by the Gemini key pool.

    Point any OpenAI SDK / LangChain / etc. at this gateway's base_url with
    a `gwk_...` token as the API key, and `model="gemini-3.5-flash"` (or any
    other Gemini model name) — no other client-side changes needed. Request
    and response are translated to/from Gemini's format; failover across
    the key pool is unchanged (see GatewayService).

    Non-streaming only for now — see translation.py docstring for scope.
    """
    try:
        provider = get_provider(_PROVIDER_TYPE.value)
    except ProviderNotSupportedError as exc:
        return _openai_error(404, str(exc), "invalid_request_error")

    gemini_payload = openai_request_to_gemini_payload(request)
    path = gemini_path_for_model(request.model)

    try:
        upstream_response = await gateway.proxy_request(
            provider=provider,
            provider_type=_PROVIDER_TYPE,
            path=path,
            method="POST",
            payload=gemini_payload,
            headers={},
        )
    except NoAvailableKeysError as exc:
        return _openai_error(503, str(exc), "no_available_keys")
    except UpstreamExhaustedError as exc:
        return _openai_error(503, str(exc), "upstream_exhausted")

    if upstream_response.status_code >= 400:
        # Surface Gemini's own error body rather than reshaping it — callers
        # debugging a bad model name / bad request want to see the real
        # upstream message, not a generic wrapper.
        try:
            detail = upstream_response.json()
        except json.JSONDecodeError:
            detail = upstream_response.text
        return _openai_error(upstream_response.status_code, str(detail), "upstream_error")

    gemini_body = upstream_response.json()
    openai_response = gemini_response_to_openai(gemini_body, model=request.model)
    return JSONResponse(status_code=200, content=openai_response.model_dump())
