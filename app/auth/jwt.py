import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt

from app.config import get_settings


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str


class InvalidTokenError(Exception):
    pass


class TokenExpiredError(Exception):
    pass


def _encode(*, subject: str, token_type: str, expires_delta: timedelta) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        "jti": secrets.token_urlsafe(8),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    return _encode(
        subject=str(user_id),
        token_type="access",
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: int) -> str:
    settings = get_settings()
    return _encode(
        subject=str(user_id),
        token_type="refresh",
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def issue_token_pair(user_id: int) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


def decode_token(token: str, *, expected_type: str) -> int:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError() from exc
    except jwt.InvalidTokenError as exc:
        raise InvalidTokenError() from exc

    if payload.get("type") != expected_type:
        raise InvalidTokenError()

    try:
        return int(payload["sub"])
    except (KeyError, ValueError, TypeError) as exc:
        raise InvalidTokenError() from exc


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
