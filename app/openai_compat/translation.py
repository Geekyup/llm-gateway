from app.openai_compat.schemas import (
    ChatCompletionChoice,
    ChatCompletionChoiceMessage,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionUsage,
)

_GEMINI_ROLE_MAP = {"user": "user", "assistant": "model"}


def gemini_path_for_model(model: str) -> str:
    return f"v1beta/models/{model}:generateContent"


def gemini_stream_path_for_model(model: str) -> str:
    return f"v1beta/models/{model}:streamGenerateContent?alt=sse"


def gemini_stream_chunk_to_openai_delta(gemini_chunk: dict) -> tuple[str, str | None]:
    candidates = gemini_chunk.get("candidates") or []
    if not candidates:
        return "", None

    first = candidates[0]
    parts = (first.get("content") or {}).get("parts") or []
    text = "".join(part.get("text", "") for part in parts)

    raw_reason = first.get("finishReason")
    if not raw_reason:
        return text, None
    raw_reason = raw_reason.lower()
    finish_reason = "length" if raw_reason == "max_tokens" else "stop" if raw_reason == "stop" else raw_reason
    return text, finish_reason


def openai_request_to_gemini_payload(request: ChatCompletionRequest) -> dict:
    system_parts: list[str] = []
    contents: list[dict] = []

    for message in request.messages:
        if message.role == "system":
            system_parts.append(message.content)
            continue
        gemini_role = _GEMINI_ROLE_MAP.get(message.role, "user")
        contents.append({"role": gemini_role, "parts": [{"text": message.content}]})

    payload: dict = {"contents": contents}

    if system_parts:
        payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}

    generation_config: dict = {}
    if request.temperature is not None:
        generation_config["temperature"] = request.temperature
    if request.max_tokens is not None:
        generation_config["maxOutputTokens"] = request.max_tokens
    if generation_config:
        payload["generationConfig"] = generation_config

    return payload


def gemini_response_to_openai(gemini_body: dict, *, model: str) -> ChatCompletionResponse:
    candidates = gemini_body.get("candidates") or []
    text = ""
    finish_reason = "stop"
    if candidates:
        first = candidates[0]
        parts = (first.get("content") or {}).get("parts") or []
        text = "".join(part.get("text", "") for part in parts)
        raw_reason = (first.get("finishReason") or "STOP").lower()
        finish_reason = "length" if raw_reason == "max_tokens" else "stop" if raw_reason == "stop" else raw_reason

    usage = gemini_body.get("usageMetadata") or {}

    return ChatCompletionResponse(
        model=model,
        choices=[
            ChatCompletionChoice(
                message=ChatCompletionChoiceMessage(content=text),
                finish_reason=finish_reason,
            )
        ],
        usage=ChatCompletionUsage(
            prompt_tokens=usage.get("promptTokenCount", 0),
            completion_tokens=usage.get("candidatesTokenCount", 0),
            total_tokens=usage.get("totalTokenCount", 0),
        ),
    )
