import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.deps import get_gateway_service
from app.core.exceptions import NoAvailableKeysError, ProviderNotSupportedError, UpstreamExhaustedError
from app.gateway.dependencies import require_gateway_token
from app.gateway.proxy_service import GatewayService
from app.keys.enums import ProviderType
from app.openai_compat.schemas import ChatCompletionRequest, OpenAIErrorDetail, OpenAIErrorResponse
from app.openai_compat.translation import (
    gemini_path_for_model,
    gemini_response_to_openai,
    openai_request_to_gemini_payload,
)
from app.providers.registry import get_provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["openai-compat"])


def _openai_error(status_code: int, message: str, error_type: str) -> JSONResponse:
    body = OpenAIErrorResponse(error=OpenAIErrorDetail(message=message, type=error_type))
    return JSONResponse(status_code=status_code, content=body.model_dump())


@router.post("/chat/completions", operation_id="openai_chat_completions")
async def chat_completions(
    request: ChatCompletionRequest,
    gateway: GatewayService = Depends(get_gateway_service),
    user_id: int = Depends(require_gateway_token),
):
    """OpenAI-compatible chat completions, backed by whichever provider's
    key pool `request.provider` selects (defaults to "gemini" so existing
    clients that don't send it keep working unchanged).

    Point any OpenAI SDK / LangChain / etc. at this gateway's base_url with
    a `gwk_...` token as the API key. Failover across the key pool is
    unchanged regardless of provider (see GatewayService).

    Gemini isn't natively OpenAI-compatible, so its request/response are
    translated (see translation.py). OpenRouter *is* OpenAI-compatible
    already, so its payload passes through close to 1:1.

    Non-streaming only for now — see translation.py docstring for scope.
    """
    try:
        provider_type = ProviderType(request.provider)
    except ValueError:
        return _openai_error(
            400,
            f"Unknown provider '{request.provider}'. Supported: {', '.join(p.value for p in ProviderType)}",
            "invalid_request_error",
        )

    try:
        provider = get_provider(provider_type.value)
    except ProviderNotSupportedError as exc:
        return _openai_error(404, str(exc), "invalid_request_error")

    if provider_type is ProviderType.GEMINI:
        upstream_payload = openai_request_to_gemini_payload(request)
        path = gemini_path_for_model(request.model)
    else:
        # OpenRouter (and any future OpenAI-compatible provider): forward
        # the request close to as-is, stripping only our own routing field.
        upstream_payload = request.model_dump(exclude={"provider"}, exclude_none=True)
        path = "v1/chat/completions"

    try:
        upstream_response = await gateway.proxy_request(
            user_id=user_id,
            provider=provider,
            provider_type=provider_type,
            path=path,
            method="POST",
            payload=upstream_payload,
            headers={},
        )
    except NoAvailableKeysError as exc:
        return _openai_error(503, str(exc), "no_available_keys")
    except UpstreamExhaustedError as exc:
        return _openai_error(503, str(exc), "upstream_exhausted")

    if upstream_response.status_code >= 400:
        # Surface the upstream's own error body rather than reshaping it —
        # callers debugging a bad model name / bad request want to see the
        # real upstream message, not a generic wrapper.
        try:
            detail = upstream_response.json()
        except json.JSONDecodeError:
            detail = upstream_response.text
        return _openai_error(upstream_response.status_code, str(detail), "upstream_error")

    upstream_body = upstream_response.json()
    if provider_type is ProviderType.GEMINI:
        openai_response = gemini_response_to_openai(upstream_body, model=request.model)
        return JSONResponse(status_code=200, content=openai_response.model_dump())

    # OpenRouter already returns an OpenAI-shaped body — pass it straight
    # through rather than round-tripping it through our own schema.
    return JSONResponse(status_code=200, content=upstream_body)
