from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.deps import get_gateway_token_service
from app.tokens.service import GatewayTokenService

_bearer_scheme = HTTPBearer(auto_error=True)


async def require_gateway_token(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    token_service: GatewayTokenService = Depends(get_gateway_token_service),
) -> int:
    user_id = await token_service.authenticate(credentials.credentials)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked gateway token")
    return user_id
