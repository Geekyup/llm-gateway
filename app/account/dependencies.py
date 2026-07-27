from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings

_bearer_scheme = HTTPBearer(auto_error=True)


def require_admin(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> None:
    """Single static bearer token from settings.

    NOT currently wired to any router — key and gateway-token CRUD moved to
    /me/* under per-user JWT auth (see auth/deps.get_current_user) once the
    key pool and tokens became per-account rather than one shared pool.
    Kept available for any future operator-only, cross-account action
    (e.g. a system-wide admin dashboard) that genuinely needs to bypass
    per-user scoping — do not reintroduce it as a substitute for
    get_current_user on anything that touches one user's own data.
    """
    if credentials.credentials != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin credentials")
