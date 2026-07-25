import time
import uuid

from pydantic import BaseModel, Field

# ─── Request (subset of the OpenAI chat/completions schema) ────────────────
# Only what's needed for a plain, non-streaming text chat. Anything else
# (tools, function calling, images, streaming) is out of scope for now —
# see ADR note in README / commit message for why.


class ChatMessage(BaseModel):
    role: str  # "system" | "user" | "assistant"
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    temperature: float | None = None
    max_tokens: int | None = None


# ─── Response (OpenAI chat/completions response shape) ─────────────────────


class ChatCompletionChoiceMessage(BaseModel):
    role: str = "assistant"
    content: str


class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: ChatCompletionChoiceMessage
    finish_reason: str = "stop"


class ChatCompletionUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: list[ChatCompletionChoice]
    usage: ChatCompletionUsage


class OpenAIErrorDetail(BaseModel):
    message: str
    type: str
    code: str | None = None


class OpenAIErrorResponse(BaseModel):
    error: OpenAIErrorDetail
