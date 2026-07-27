from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GatewayTokenCreate(BaseModel):
    label: str = Field(..., max_length=255)


class GatewayTokenRead(BaseModel):
    id: int
    label: str
    token_preview: str
    is_active: bool
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GatewayTokenCreated(BaseModel):
    token: GatewayTokenRead
    plaintext: str
