"""Access/refresh JWT helpers.

Two token types, both signed with the same JWT_SECRET_KEY but carrying a
"type" claim so one can never be mistaken for the other:

- access:  short-lived (ACCESS_TOKEN_EXPIRE_MINUTES), sent as a Bearer
  token on every API call, never stored server-side.
- refresh: long-lived (REFRESH_TOKEN_EXPIRE_DAYS), used only to mint new
  access tokens. Its hash is stored in the refresh_tokens table so it can
  be revoked (logout, reuse-detection) — the raw value never is.
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt

from app.config import get_settings


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str


class InvalidTokenError(Exception):
    """Raised for any JWT that fails to decode/verify — bad signature, malformed, wrong type."""


class TokenExpiredError(Exception):
    """Raised specifically for an expired-but-otherwise-valid token, so callers can distinguish."""


def _encode(*, subject: str, token_type: str, expires_delta: timedelta) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        # jti gives every refresh token a unique identity independent of its
        # hash, mostly useful for audit logging if that's ever added.
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
    """Verify signature + expiry + type, and return the user_id (sub claim).

    Raises TokenExpiredError / InvalidTokenError rather than the raw
    PyJWT exceptions so calling code doesn't need to import jwt itself.
    """
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
    """One-way hash stored in the DB in place of the raw refresh token.

    SHA-256 (not bcrypt/argon2) is appropriate here: unlike a password,
    a refresh token is already a long random-looking secret, not
    something a human chose — there's no low-entropy input to protect
    against offline brute-forcing.
    """
    return hashlib.sha256(token.encode()).hexdigest()
