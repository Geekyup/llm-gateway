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


class APIKeyBulkCreate(BaseModel):
    provider: ProviderType
    raw_keys: str = Field(
        ...,
        description="Raw API keys separated by newlines, commas, or whitespace. Duplicates and blanks are ignored.",
    )
    label_prefix: str = Field(default="Key", max_length=240)
    daily_limit: int = Field(..., gt=0)
    model: str | None = Field(default=None, max_length=128)


class APIKeyBulkCreateError(BaseModel):
    raw_key_preview: str
    detail: str


class APIKeyBulkCreateResult(BaseModel):
    created: list["APIKeyRead"]
    skipped_duplicates: int
    errors: list[APIKeyBulkCreateError]


class APIKeyUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=255)
    status: KeyStatus | None = None
    daily_limit: int | None = Field(default=None, gt=0)
    model: str | None = Field(default=None, max_length=128)


class APIKeyRead(BaseModel):
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

    model_config = ConfigDict(from_attributes=True)

class APIKeyHealthCheckResult(BaseModel):
    key_id: int
    ok: bool
    detail: str | None = Field(default=None, description="Reason for failure; never set when ok=True")


class APIKeyDTO(BaseModel):
    id: int
    user_id: int
    label: str
    provider: ProviderType
    status: KeyStatus
    requests_today: int
    daily_limit: int
    model: str | None = None
    decrypted_key: str | None = None

    model_config = ConfigDict(from_attributes=True)