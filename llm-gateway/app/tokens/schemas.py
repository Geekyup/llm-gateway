from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GatewayTokenCreate(BaseModel):
    label: str = Field(..., max_length=255)


class GatewayTokenRead(BaseModel):
    """Metadata only — never includes the plaintext token."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    token_preview: str
    is_active: bool
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime


class GatewayTokenCreated(BaseModel):
    """Returned exactly once, right after creation — the only time the
    plaintext token is ever available. The caller must copy it now.
    """

    token: GatewayTokenRead
    plaintext: str
