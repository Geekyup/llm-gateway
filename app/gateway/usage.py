import logging

import httpx

from app.gateway.attempts import NO_USAGE, TokenUsage

logger = logging.getLogger(__name__)


def extract_usage(response: httpx.Response) -> TokenUsage:
    try:
        body = response.json()
        if "usageMetadata" in body:
            return _from_gemini(body["usageMetadata"] or {})
        return _from_openai(body.get("usage") or {})
    except Exception:
        logger.warning("failed to parse usage data for token accounting", exc_info=True)
        return NO_USAGE


def _from_gemini(metadata: dict) -> TokenUsage:
    return TokenUsage(
        prompt=metadata.get("promptTokenCount"),
        completion=metadata.get("candidatesTokenCount"),
        total=metadata.get("totalTokenCount"),
    )


def _from_openai(usage: dict) -> TokenUsage:
    return TokenUsage(
        prompt=usage.get("prompt_tokens"),
        completion=usage.get("completion_tokens"),
        total=usage.get("total_tokens"),
    )
