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
    status_code = 503
    detail = "No available API keys for provider '{provider}'"


class UpstreamExhaustedError(LLMGatewayError):
    status_code = 503
    detail = "All {attempts} candidate key(s) for '{provider}' were rate-limited or exhausted"


class KeyNotFoundError(LLMGatewayError):
    status_code = 404
    detail = "API key with id={key_id} not found"


class ProviderNotSupportedError(LLMGatewayError):
    status_code = 404
    detail = "Provider '{provider}' is not registered"


class ProviderRequestError(LLMGatewayError):
    status_code = 502
    detail = "Request to '{provider}' failed: {reason}"


class GatewayTokenNotFoundError(LLMGatewayError):
    status_code = 404
    detail = "Gateway token with id={token_id} not found"


class InactiveUserError(LLMGatewayError):
    status_code = 403
    detail = "This account has been deactivated"


class TokenRevokedError(LLMGatewayError):
    status_code = 401
    detail = "Refresh token has been revoked"
