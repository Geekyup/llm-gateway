from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.keys.enums import KeyStatus, ProviderType


class APIKeyCreate(BaseModel):
    label: str = Field(..., max_length=255)
    provider: ProviderType
    raw_key: str = Field(..., description="Plaintext API key. Encrypted before storage, never persisted as-is.")
    daily_limit: int = Field(..., gt=0)
    model: str | None = Field(
        default=None,
        max_length=128,
        description="Upstream model this key serves, e.g. 'gemini-3.6-flash' or 'openai/gpt-4o-mini'. "
        "If unset, this key is only used for requests that also don't specify a model.",
    )


class APIKeyUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=255)
    status: KeyStatus | None = None
    daily_limit: int | None = Field(default=None, gt=0)
    model: str | None = Field(default=None, max_length=128)


class APIKeyRead(BaseModel):
    """Never includes the decrypted key — admin endpoints only expose metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    provider: ProviderType
    status: KeyStatus
    requests_today: int
    daily_limit: int
    model: str | None
    cooldown_until: datetime | None
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime


class APIKeyHealthCheckResult(BaseModel):
    """Response for a health-check probe — either a single POST /{id}/check
    or one entry in the list returned by POST /check-all.
    """

    key_id: int
    ok: bool
    detail: str | None = Field(default=None, description="Reason for failure; never set when ok=True")


class APIKeyDTO(BaseModel):
    """Internal, in-process transfer object used by selector/cache/service.

    Distinct from APIKeyRead: this one MAY carry the decrypted key when
    the gateway needs it to make an upstream call, so it must never be
    returned directly from an HTTP endpoint.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    label: str
    provider: ProviderType
    status: KeyStatus
    requests_today: int
    daily_limit: int
    model: str | None = None
    decrypted_key: str | None = None
