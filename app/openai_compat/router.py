import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse

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
from app.openai_compat.schemas import (
    ChatCompletionChunk,
    ChatCompletionChunkChoice,
    ChatCompletionChunkDelta,
    ChatCompletionRequest,
    OpenAIErrorDetail,
    OpenAIErrorResponse,
)
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
    return await run_chat_completion(request, gateway=gateway, user_id=user_id)


async def run_chat_completion(
    request: ChatCompletionRequest,
    *,
    gateway: GatewayService,
    user_id: int,
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
    default_groq_model = get_settings().DEFAULT_GROQ_MODEL


    def build_request(dto: APIKeyDTO) -> UpstreamRequestSpec:
        if dto.provider is ProviderType.GEMINI:
            gemini_model = dto.model or requested_model or default_gemini_model
            return UpstreamRequestSpec(
                path=gemini_path_for_model(gemini_model),
                method="POST",
                payload=openai_request_to_gemini_payload(request),
                headers={},
            )
        default_model = default_groq_model if dto.provider is ProviderType.GROQ else default_openrouter_model
        payload = request.model_dump(exclude={"provider"}, exclude_none=True)
        payload["model"] = dto.model or requested_model or default_model
        payload["stream"] = False
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
    is_gemini_shape = "candidates" in upstream_body or "usageMetadata" in upstream_body
    if is_gemini_shape:
        openai_response = gemini_response_to_openai(
            upstream_body, model=requested_model or default_gemini_model
        )
        response_model = openai_response.model
        content = openai_response.choices[0].message.content if openai_response.choices else ""
        json_body = openai_response.model_dump()
    else:
        response_model = upstream_body.get("model", requested_model or default_gemini_model)
        choices = upstream_body.get("choices") or []
        content = (choices[0].get("message") or {}).get("content") if choices else ""
        json_body = upstream_body

    content = content or ""

    if not request.stream:
        return JSONResponse(status_code=200, content=json_body)

    return StreamingResponse(
        _emulated_stream(content, model=response_model),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _emulated_stream(content: str, *, model: str):
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"

    def chunk(delta: ChatCompletionChunkDelta, finish_reason: str | None = None) -> str:
        payload = ChatCompletionChunk(
            id=completion_id,
            model=model,
            choices=[ChatCompletionChunkChoice(delta=delta, finish_reason=finish_reason)],
        )
        return f"data: {json.dumps(payload.model_dump())}\n\n"

    try:
        yield chunk(ChatCompletionChunkDelta(role="assistant", content=""))

        words = (content or "").split(" ")
        for i, word in enumerate(words):
            piece = word if i == len(words) - 1 else word + " "
            yield chunk(ChatCompletionChunkDelta(content=piece))
            await asyncio.sleep(0.02)

        yield chunk(ChatCompletionChunkDelta(), finish_reason="stop")
        yield "data: [DONE]\n\n"
    except Exception:
        logger.exception("emulated stream failed after headers were sent")
        error_payload = {
            "error": {"message": "Streaming failed while generating the response.", "type": "internal_error"}
        }
        yield f"data: {json.dumps(error_payload)}\n\n"
        yield "data: [DONE]\n\n"