import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from app.auth.deps import get_auth_service, get_current_user
from app.auth.jwt import InvalidTokenError, TokenExpiredError
from app.auth.models import User
from app.auth.oauth import oauth
from app.auth.schemas import RefreshRequest, TokenPairRead, UserRead
from app.auth.service import AuthService
from app.config import get_settings
from app.core.exceptions import InactiveUserError, TokenRevokedError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/google/login")
async def google_login(request: Request):
    """Kicks off the OAuth dance: redirects the browser to Google's consent screen.

    The nonce is stashed in the signed session cookie (see SessionMiddleware
    in main.py) and re-checked in the callback below — this is what stops
    an attacker from replaying someone else's callback URL.
    """
    settings = get_settings()
    request.session["oauth_nonce"] = secrets.token_urlsafe(16)
    return await oauth.google.authorize_redirect(
        request, settings.GOOGLE_REDIRECT_URI, nonce=request.session["oauth_nonce"]
    )


@router.get("/google/callback")
async def google_callback(
    request: Request,
    service: Annotated[AuthService, Depends(get_auth_service)],
):
    """Google redirects back here after the person approves/denies access.

    Issues our own access/refresh pair and hands them to the frontend via
    a redirect with the tokens in the URL fragment (never sent to the
    server on the next request, unlike a query string) rather than a
    JSON body, since this endpoint is reached by full-page browser
    navigation, not an API call the SPA controls directly.
    """
    settings = get_settings()
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as exc:  # noqa: BLE001 - authlib raises several distinct error types here
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google sign-in failed") from exc

    nonce = request.session.get("oauth_nonce")
    user_info = await oauth.google.parse_id_token(token, nonce=nonce)
    if not user_info or not user_info.get("sub"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google sign-in failed")

    try:
        _, pair = await service.login_with_google(
            google_sub=user_info["sub"],
            email=user_info.get("email", ""),
            display_name=user_info.get("name"),
            avatar_url=user_info.get("picture"),
        )
    except InactiveUserError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account has been deactivated")

    frontend_url = settings.CORS_ORIGINS[0] if settings.CORS_ORIGINS else "/"
    return RedirectResponse(
        f"{frontend_url}/#access_token={pair.access_token}&refresh_token={pair.refresh_token}"
    )


@router.post("/refresh", response_model=TokenPairRead)
async def refresh(
    data: RefreshRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
):
    try:
        pair = await service.refresh(data.refresh_token)
    except TokenExpiredError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")
    except (InvalidTokenError, TokenRevokedError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    return TokenPairRead(access_token=pair.access_token, refresh_token=pair.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    data: RefreshRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> None:
    await service.logout(data.refresh_token)


@router.get("/me", response_model=UserRead)
async def me(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user
