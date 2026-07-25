from pydantic import BaseModel


class GatewayErrorBody(BaseModel):
    error: str
    provider: str
    detail: str | None = None
