from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from llm_gateway.api.deps import get_gateway_token_service
from llm_gateway.tokens.service import GatewayTokenService

_bearer_scheme = HTTPBearer(auto_error=True)


async def require_gateway_token(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    token_service: GatewayTokenService = Depends(get_gateway_token_service),
) -> None:
    """Guards POST/GET /v1/{provider}/... — the client-facing proxy.

    Distinct from require_admin (which guards /admin/*): this checks a
    GatewayToken generated via the dashboard, not the ADMIN_API_KEY. Any
    application calling the unified pool must present one of these.
    """
    if not await token_service.verify(credentials.credentials):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked gateway token")
