"""Translates between the OpenAI chat/completions wire format and Gemini's
generateContent format, so clients can point any OpenAI-compatible SDK
(openai-python, LangChain, etc.) at this gateway with base_url + api_key
and nothing else changes.

Deliberately narrow: text-only messages, no streaming, no tool calls, no
images. Extend here as those needs come up rather than guessing ahead.
"""

from llm_gateway.openai_compat.schemas import (
    ChatCompletionChoice,
    ChatCompletionChoiceMessage,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionUsage,
)

# Gemini has no "system" role — system messages are folded into
# systemInstruction instead, per Gemini's own convention.
_GEMINI_ROLE_MAP = {"user": "user", "assistant": "model"}


def gemini_path_for_model(model: str) -> str:
    """e.g. "gemini-3.5-flash" -> "v1beta/models/gemini-3.5-flash:generateContent" """
    return f"v1beta/models/{model}:generateContent"


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
        # Gemini's finishReason ("STOP", "MAX_TOKENS", ...) roughly maps to
        # OpenAI's ("stop", "length", ...); anything unrecognised passes
        # through lowercased rather than being silently dropped.
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
