from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from llm_gateway.keys.enums import KeyStatus, ProviderType


class APIKeyCreate(BaseModel):
    label: str = Field(..., max_length=255)
    provider: ProviderType
    raw_key: str = Field(..., description="Plaintext API key. Encrypted before storage, never persisted as-is.")
    daily_limit: int = Field(..., gt=0)


class APIKeyUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=255)
    status: KeyStatus | None = None
    daily_limit: int | None = Field(default=None, gt=0)


class APIKeyRead(BaseModel):
    """Never includes the decrypted key — admin endpoints only expose metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    provider: ProviderType
    status: KeyStatus
    requests_today: int
    daily_limit: int
    cooldown_until: datetime | None
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime


class APIKeyDTO(BaseModel):
    """Internal, in-process transfer object used by selector/cache/service.

    Distinct from APIKeyRead: this one MAY carry the decrypted key when
    the gateway needs it to make an upstream call, so it must never be
    returned directly from an HTTP endpoint.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    provider: ProviderType
    status: KeyStatus
    requests_today: int
    daily_limit: int
    decrypted_key: str | None = None
