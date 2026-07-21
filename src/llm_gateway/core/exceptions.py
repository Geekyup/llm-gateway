class LLMGatewayError(Exception):
    """Base class for all domain exceptions."""


class NoAvailableKeysError(LLMGatewayError):
    """Raised when the pool has no active key for the requested provider."""

    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__(f"No available API keys for provider '{provider}'")


class UpstreamExhaustedError(LLMGatewayError):
    """Raised when every candidate key was tried and all were rate-limited/exhausted."""

    def __init__(self, provider: str, attempts: int) -> None:
        self.provider = provider
        self.attempts = attempts
        super().__init__(
            f"All {attempts} candidate key(s) for '{provider}' were rate-limited or exhausted"
        )


class KeyNotFoundError(LLMGatewayError):
    def __init__(self, key_id: int) -> None:
        self.key_id = key_id
        super().__init__(f"API key with id={key_id} not found")


class GatewayTokenNotFoundError(LLMGatewayError):
    def __init__(self, token_id: int) -> None:
        self.token_id = token_id
        super().__init__(f"Gateway token with id={token_id} not found")


class ProviderNotSupportedError(LLMGatewayError):
    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__(f"Provider '{provider}' is not registered")
