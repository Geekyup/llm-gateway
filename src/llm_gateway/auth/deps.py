from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from llm_gateway.auth.jwt import InvalidTokenError, TokenExpiredError, decode_token
from llm_gateway.auth.models import User
from llm_gateway.auth.repository import RefreshTokenRepository, UserRepository
from llm_gateway.auth.service import AuthService
from llm_gateway.db.session import get_db

_bearer_scheme = HTTPBearer(auto_error=True)


def get_user_repository(session: Annotated[AsyncSession, Depends(get_db)]) -> UserRepository:
    return UserRepository(session)


def get_refresh_token_repository(session: Annotated[AsyncSession, Depends(get_db)]) -> RefreshTokenRepository:
    return RefreshTokenRepository(session)


def get_auth_service(
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    token_repo: Annotated[RefreshTokenRepository, Depends(get_refresh_token_repository)],
) -> AuthService:
    return AuthService(user_repo, token_repo)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> User:
    """Every /me/* endpoint depends on this — it's the actual data boundary.

    A valid access token only proves *who* the caller is; it's this
    lookup (not the token) that a query then filters by, e.g.
    APIKeyRepository.list_all(user_id=user.id).
    """
    try:
        user_id = decode_token(credentials.credentials, expected_type="access")
    except TokenExpiredError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Access token expired")
    except InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")

    user = await user_repo.get(user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    return user
