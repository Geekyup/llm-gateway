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
    gemini_stream_chunk_to_openai_delta,
    gemini_stream_path_for_model,
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


    def build_request(dto: APIKeyDTO, *, stream: bool) -> UpstreamRequestSpec:
        if dto.provider is ProviderType.GEMINI:
            gemini_model = dto.model or requested_model or default_gemini_model
            path = gemini_stream_path_for_model(gemini_model) if stream else gemini_path_for_model(gemini_model)
            return UpstreamRequestSpec(
                path=path,
                method="POST",
                payload=openai_request_to_gemini_payload(request),
                headers={},
            )
        default_model = default_groq_model if dto.provider is ProviderType.GROQ else default_openrouter_model
        payload = request.model_dump(exclude={"provider"}, exclude_none=True)
        payload["model"] = dto.model or requested_model or default_model
        payload["stream"] = stream
        return UpstreamRequestSpec(
            path="v1/chat/completions",
            method="POST",
            payload=payload,
            headers={},
        )

    if not request.stream:
        return await _handle_non_streaming(
            request,
            gateway=gateway,
            user_id=user_id,
            provider_type=provider_type,
            requested_model=requested_model,
            default_gemini_model=default_gemini_model,
            build_request=lambda dto: build_request(dto, stream=False),
        )

    return await _handle_streaming(
        gateway=gateway,
        user_id=user_id,
        provider_type=provider_type,
        requested_model=requested_model,
        default_gemini_model=default_gemini_model,
        build_request=lambda dto: build_request(dto, stream=True),
    )


async def _handle_non_streaming(
    request: ChatCompletionRequest,
    *,
    gateway: GatewayService,
    user_id: int,
    provider_type: ProviderType | None,
    requested_model: str | None,
    default_gemini_model: str,
    build_request,
):
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
        json_body = openai_response.model_dump()
    else:
        json_body = upstream_body

    return JSONResponse(status_code=200, content=json_body)


class _UpstreamErrorSignal(Exception):

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


async def _handle_streaming(
    *,
    gateway: GatewayService,
    user_id: int,
    provider_type: ProviderType | None,
    requested_model: str | None,
    default_gemini_model: str,
    build_request,
):
    generator = _open_and_relay_stream(
        gateway,
        user_id=user_id,
        provider_type=provider_type,
        requested_model=requested_model,
        default_gemini_model=default_gemini_model,
        build_request=build_request,
    )
    try:
        first_chunk = await generator.__anext__()
    except StopAsyncIteration:
        first_chunk = None
    except NoAvailableKeysError as exc:
        return _openai_error(503, str(exc), "no_available_keys")
    except UpstreamExhaustedError as exc:
        return _openai_error(503, str(exc), "upstream_exhausted")
    except ProviderNotSupportedError as exc:
        return _openai_error(404, str(exc), "invalid_request_error")
    except _UpstreamErrorSignal as exc:
        return _openai_error(exc.status_code, exc.detail, "upstream_error")

    async def _iter_with_first():
        if first_chunk is not None:
            yield first_chunk
        async for chunk in generator:
            yield chunk

    return StreamingResponse(
        _iter_with_first(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _open_and_relay_stream(
    gateway: GatewayService,
    *,
    user_id: int,
    provider_type: ProviderType | None,
    requested_model: str | None,
    default_gemini_model: str,
    build_request,
):
    async with gateway.proxy_stream_request(
        user_id=user_id,
        build_request=build_request,
        provider_type=provider_type,
        model=requested_model,
    ) as upstream_response:
        if upstream_response.status_code >= 400:
            body = await upstream_response.aread()
            try:
                detail = json.loads(body)
            except json.JSONDecodeError:
                detail = body.decode(errors="replace")
            raise _UpstreamErrorSignal(upstream_response.status_code, str(detail))

        is_gemini = "streamGenerateContent" in str(upstream_response.request.url)
        if is_gemini:
            relay = _relay_gemini_stream(upstream_response, model=requested_model or default_gemini_model)
        else:
            relay = _relay_openai_stream(upstream_response)

        async for chunk in relay:
            yield chunk


async def _relay_openai_stream(upstream_response):
    async for line in upstream_response.aiter_lines():
        if not line:
            continue
        yield f"{line}\n\n"


async def _relay_gemini_stream(upstream_response, *, model: str):
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"

    def chunk(delta: ChatCompletionChunkDelta, finish_reason: str | None = None) -> str:
        payload = ChatCompletionChunk(
            id=completion_id,
            model=model,
            choices=[ChatCompletionChunkChoice(delta=delta, finish_reason=finish_reason)],
        )
        return f"data: {json.dumps(payload.model_dump())}\n\n"

    yield chunk(ChatCompletionChunkDelta(role="assistant", content=""))

    async for line in upstream_response.aiter_lines():
        if not line.startswith("data:"):
            continue
        raw = line.removeprefix("data:").strip()
        if not raw or raw == "[DONE]":
            continue
        try:
            gemini_chunk = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("failed to parse gemini SSE chunk", exc_info=True)
            continue

        text, finish_reason = gemini_stream_chunk_to_openai_delta(gemini_chunk)
        if text:
            yield chunk(ChatCompletionChunkDelta(content=text))
        if finish_reason:
            yield chunk(ChatCompletionChunkDelta(), finish_reason=finish_reason)

    yield "data: [DONE]\n\n"