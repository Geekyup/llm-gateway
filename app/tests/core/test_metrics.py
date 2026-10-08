from prometheus_client import REGISTRY

from app.core.metrics import observe_attempt


def _sample(name: str, **labels) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


def test_observe_attempt_counts_attempts_by_provider_and_outcome():
    before = _sample("gateway_upstream_attempts_total", provider="groq", outcome="rate_limited")

    observe_attempt(provider="groq", outcome="rate_limited", latency_ms=120)

    after = _sample("gateway_upstream_attempts_total", provider="groq", outcome="rate_limited")
    assert after - before == 1


def test_observe_attempt_records_latency_in_seconds():
    before_sum = _sample("gateway_upstream_latency_seconds_sum", provider="groq", outcome="success")
    before_count = _sample("gateway_upstream_latency_seconds_count", provider="groq", outcome="success")

    observe_attempt(provider="groq", outcome="success", latency_ms=250)

    assert _sample("gateway_upstream_latency_seconds_sum", provider="groq", outcome="success") - before_sum == 0.25
    assert _sample("gateway_upstream_latency_seconds_count", provider="groq", outcome="success") - before_count == 1


def test_attempts_that_never_reached_the_provider_have_no_latency_sample():
    before = _sample("gateway_upstream_latency_seconds_count", provider="any", outcome="no_keys")

    observe_attempt(provider="any", outcome="no_keys", latency_ms=None)

    assert _sample("gateway_upstream_latency_seconds_count", provider="any", outcome="no_keys") == before
    assert _sample("gateway_upstream_attempts_total", provider="any", outcome="no_keys") >= 1


def test_tokens_are_counted_only_for_successful_attempts():
    before_prompt = _sample("gateway_tokens_total", provider="openrouter", kind="prompt")
    before_completion = _sample("gateway_tokens_total", provider="openrouter", kind="completion")

    observe_attempt(provider="openrouter", outcome="success", latency_ms=10, prompt_tokens=7, completion_tokens=3)
    observe_attempt(provider="openrouter", outcome="error", latency_ms=10, prompt_tokens=100, completion_tokens=100)

    assert _sample("gateway_tokens_total", provider="openrouter", kind="prompt") - before_prompt == 7
    assert _sample("gateway_tokens_total", provider="openrouter", kind="completion") - before_completion == 3
