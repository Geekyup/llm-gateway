from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from llm_gateway.api.deps import get_gateway_token_service
from llm_gateway.tokens.service import GatewayTokenService

_bearer_scheme = HTTPBearer(auto_error=True)


async def require_gateway_token(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    token_service: GatewayTokenService = Depends(get_gateway_token_service),
) -> int:
    """Guards POST/GET /v1/{provider}/... — the client-facing proxy.

    Distinct from require_admin (available for future cross-account
    operator actions): this checks a GatewayToken generated via the
    dashboard, not the ADMIN_API_KEY. Any application calling the unified
    pool must present one of these.

    Returns the user_id that owns the token, which the router then passes
    into GatewayService so the request can only ever draw from that
    user's own key pool — never anyone else's.
    """
    user_id = await token_service.authenticate(credentials.credentials)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked gateway token")
    return user_id
