from app.openai_compat.schemas import ChatCompletionRequest
from app.openai_compat.translation import (
    gemini_path_for_model,
    gemini_response_to_openai,
    openai_request_to_gemini_payload,
)


def test_gemini_path_for_model() -> None:
    assert gemini_path_for_model("gemini-3.5-flash") == "v1beta/models/gemini-3.5-flash:generateContent"


def test_openai_request_maps_user_and_assistant_roles() -> None:
    request = ChatCompletionRequest(
        model="gemini-3.5-flash",
        messages=[
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
            {"role": "user", "content": "how are you"},
        ],
    )
    payload = openai_request_to_gemini_payload(request)
    assert [c["role"] for c in payload["contents"]] == ["user", "model", "user"]
    assert "systemInstruction" not in payload


def test_system_messages_become_system_instruction() -> None:
    request = ChatCompletionRequest(
        model="gemini-3.5-flash",
        messages=[
            {"role": "system", "content": "Be terse."},
            {"role": "user", "content": "hi"},
        ],
    )
    payload = openai_request_to_gemini_payload(request)
    assert payload["systemInstruction"] == {"parts": [{"text": "Be terse."}]}
    assert len(payload["contents"]) == 1
    assert payload["contents"][0]["role"] == "user"


def test_temperature_and_max_tokens_map_to_generation_config() -> None:
    request = ChatCompletionRequest(
        model="gemini-3.5-flash",
        messages=[{"role": "user", "content": "hi"}],
        temperature=0.2,
        max_tokens=50,
    )
    payload = openai_request_to_gemini_payload(request)
    assert payload["generationConfig"] == {"temperature": 0.2, "maxOutputTokens": 50}


def test_gemini_response_to_openai_extracts_text_and_usage() -> None:
    gemini_body = {
        "candidates": [
            {
                "content": {"parts": [{"text": "hello there"}]},
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {"promptTokenCount": 3, "candidatesTokenCount": 2, "totalTokenCount": 5},
    }
    response = gemini_response_to_openai(gemini_body, model="gemini-3.5-flash")
    assert response.choices[0].message.content == "hello there"
    assert response.choices[0].finish_reason == "stop"
    assert response.usage.prompt_tokens == 3
    assert response.usage.completion_tokens == 2
    assert response.usage.total_tokens == 5


def test_gemini_response_with_no_candidates_yields_empty_content() -> None:
    response = gemini_response_to_openai({}, model="gemini-3.5-flash")
    assert response.choices[0].message.content == ""
    assert response.usage.total_tokens == 0


def test_max_tokens_finish_reason_maps_to_length() -> None:
    gemini_body = {
        "candidates": [
            {
                "content": {"parts": [{"text": "cut off"}]},
                "finishReason": "MAX_TOKENS",
            }
        ],
    }
    response = gemini_response_to_openai(gemini_body, model="gemini-3.5-flash")
    assert response.choices[0].finish_reason == "length"
