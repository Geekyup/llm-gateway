from pydantic import BaseModel


class TokenPairRead(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserRead(BaseModel):
    id: int
    email: str
    display_name: str | None
    avatar_url: str | None

    model_config = {"from_attributes": True}
