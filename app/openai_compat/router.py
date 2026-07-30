import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.deps import get_gateway_service
from app.config import get_settings
from app.core.exceptions import (
    NoAvailableKeysError,
    ProviderNotSupportedError,
    UpstreamExhaustedError,
)
from app.gateway.dependencies import require_gateway_token
from app.gateway.proxy_service import GatewayService, UpstreamRequestSpec
from app.keys.enums import ProviderType
from app.keys.schemas import APIKeyDTO
from app.openai_compat.schemas import ChatCompletionRequest, OpenAIErrorDetail, OpenAIErrorResponse
from app.openai_compat.translation import (
    gemini_path_for_model,
    gemini_response_to_openai,
    openai_request_to_gemini_payload,
)

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
    provider_type: ProviderType | None = None
    if request.provider:
        try:
            provider_type = ProviderType(request.provider)
        except ValueError:
            return _openai_error(
                400,
                f"Unknown provider '{request.provider}'. Supported: {', '.join(p.value for p in ProviderType)}",
                "invalid_request_error",
            )

    requested_model = request.model
    default_gemini_model = get_settings().DEFAULT_GEMINI_MODEL
    default_openrouter_model = get_settings().DEFAULT_OPENROUTER_MODEL


    def build_request(dto: APIKeyDTO) -> UpstreamRequestSpec:
        if dto.provider is ProviderType.GEMINI:
            gemini_model = dto.model or requested_model or default_gemini_model
            return UpstreamRequestSpec(
                path=gemini_path_for_model(gemini_model),
                method="POST",
                payload=openai_request_to_gemini_payload(request),
                headers={},
            )
        payload = request.model_dump(exclude={"provider"}, exclude_none=True)
        payload["model"] = dto.model or requested_model or default_openrouter_model
        return UpstreamRequestSpec(
            path="v1/chat/completions",
            method="POST",
            payload=payload,
            headers={},
        )

    try:
        upstream_response = await gateway.proxy_request(
            user_id=user_id,
            build_request=build_request,
            provider_type=provider_type,
            model=requested_model,
        )
    except NoAvailableKeysError as exc:
        return _openai_error(503, str(exc), "no_available_keys")
    except UpstreamExhaustedError as exc:
        return _openai_error(503, str(exc), "upstream_exhausted")
    except ProviderNotSupportedError as exc:
        return _openai_error(404, str(exc), "invalid_request_error")

    if upstream_response.status_code >= 400:
        try:
            detail = upstream_response.json()
        except json.JSONDecodeError:
            detail = upstream_response.text
        return _openai_error(upstream_response.status_code, str(detail), "upstream_error")

    upstream_body = upstream_response.json()
    if "candidates" in upstream_body or "usageMetadata" in upstream_body:
        openai_response = gemini_response_to_openai(
            upstream_body, model=requested_model or default_gemini_model
        )
        return JSONResponse(status_code=200, content=openai_response.model_dump())
    return JSONResponse(status_code=200, content=upstream_body)