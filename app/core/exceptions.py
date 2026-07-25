class LLMGatewayError(Exception):

    status_code: int = 400
    detail: str = "Application error"

    def __init__(self, detail: str | None = None, **fmt_kwargs: object) -> None:
        if fmt_kwargs:
            self.detail = self.detail.format(**fmt_kwargs)
            for key, value in fmt_kwargs.items():
                setattr(self, key, value)
        elif detail:
            self.detail = detail
        super().__init__(self.detail)


class NoAvailableKeysError(LLMGatewayError):
    """Raised when the pool has no active key for the requested provider."""

    status_code = 503
    detail = "No available API keys for provider '{provider}'"


class UpstreamExhaustedError(LLMGatewayError):
    """Raised when every candidate key was tried and all were rate-limited/exhausted."""

    status_code = 503
    detail = "All {attempts} candidate key(s) for '{provider}' were rate-limited or exhausted"


class KeyNotFoundError(LLMGatewayError):
    status_code = 404
    detail = "API key with id={key_id} not found"


class ProviderNotSupportedError(LLMGatewayError):
    status_code = 404
    detail = "Provider '{provider}' is not registered"


class GatewayTokenNotFoundError(LLMGatewayError):
    status_code = 404
    detail = "Gateway token with id={token_id} not found"


class InactiveUserError(LLMGatewayError):
    """Raised when a login attempt targets a user marked is_active=False."""

    status_code = 403
    detail = "This account has been deactivated"


class TokenRevokedError(LLMGatewayError):
    """Raised when a refresh token is unknown or was already revoked/rotated."""

    status_code = 401
    detail = "Refresh token has been revoked"
