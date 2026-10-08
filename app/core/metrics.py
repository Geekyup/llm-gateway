from prometheus_client import Counter, Gauge, Histogram

HTTP_REQUESTS = Counter(
    "http_requests_total",
    "HTTP requests handled by the API",
    ["method", "route", "status"],
)
HTTP_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60),
)
HTTP_IN_PROGRESS = Gauge("http_requests_in_progress", "HTTP requests currently being handled")

UPSTREAM_ATTEMPTS = Counter(
    "gateway_upstream_attempts_total",
    "Attempts to serve a request, by provider and outcome",
    ["provider", "outcome"],
)
UPSTREAM_LATENCY = Histogram(
    "gateway_upstream_latency_seconds",
    "Latency of attempts that reached the provider",
    ["provider", "outcome"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60),
)
TOKENS = Counter(
    "gateway_tokens_total",
    "Tokens reported by providers for successful requests",
    ["provider", "kind"],
)
RATE_LIMIT_REJECTIONS = Counter(
    "gateway_rate_limit_rejections_total",
    "Requests rejected by the per-user rate limit",
)

KEYS = Gauge("gateway_keys", "API keys by provider and status", ["provider", "status"])
EVENTS_QUEUE_LENGTH = Gauge(
    "gateway_events_queue_length",
    "Request events waiting in Redis to be written to PostgreSQL",
)

ACTIVITY_CACHE = Counter(
    "activity_cache_requests_total",
    "Activity endpoint cache lookups",
    ["endpoint", "result"],
)


def observe_attempt(
    *,
    provider: str,
    outcome: str,
    latency_ms: int | None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
) -> None:
    UPSTREAM_ATTEMPTS.labels(provider, outcome).inc()
    if latency_ms is not None:
        UPSTREAM_LATENCY.labels(provider, outcome).observe(latency_ms / 1000)
    if outcome == "success":
        if prompt_tokens:
            TOKENS.labels(provider, "prompt").inc(prompt_tokens)
        if completion_tokens:
            TOKENS.labels(provider, "completion").inc(completion_tokens)
