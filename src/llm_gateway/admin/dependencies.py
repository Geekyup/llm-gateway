from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from llm_gateway.config import Settings, get_settings

_bearer_scheme = HTTPBearer(auto_error=True)


def require_admin(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> None:
    """MVP admin auth: a single static bearer token from settings.

    Deliberately simple — swap for real user/role auth (reusing the
    template-fastapi-jwt-auth stack) once this needs multiple operators.
    """
    if credentials.credentials != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin credentials")
