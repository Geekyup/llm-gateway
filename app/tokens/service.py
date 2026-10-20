import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta

from app.tokens.cache import TokenAuthCache
from app.tokens.models import GatewayToken
from app.tokens.repository import GatewayTokenRepository
from app.tokens.schemas import GatewayTokenCreate, GatewayTokenCreated, GatewayTokenRead

logger = logging.getLogger(__name__)

_TOKEN_PREFIX = "gwk"
_TOKEN_NBYTES = 32
_LAST_USED_STALE_AFTER = timedelta(minutes=5)


def _hash_token(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode()).hexdigest()


def _preview(plaintext: str) -> str:
    return f"{plaintext[:7]}...{plaintext[-4:]}"


def _is_stale(last_used_at: datetime | None) -> bool:
    if last_used_at is None:
        return True
    if last_used_at.tzinfo is None:
        last_used_at = last_used_at.replace(tzinfo=UTC)
    return datetime.now(UTC) - last_used_at >= _LAST_USED_STALE_AFTER


class GatewayTokenService:
    def __init__(
        self, repository: GatewayTokenRepository, auth_cache: TokenAuthCache | None = None
    ) -> None:
        self._repo = repository
        self._auth_cache = auth_cache

    async def create_token(self, user_id: int, payload: GatewayTokenCreate) -> GatewayTokenCreated:
        plaintext = f"{_TOKEN_PREFIX}_{secrets.token_urlsafe(_TOKEN_NBYTES)}"
        token = await self._repo.create(
            user_id=user_id,
            label=payload.label,
            token_hash=_hash_token(plaintext),
            token_preview=_preview(plaintext),
        )
        return GatewayTokenCreated(token=GatewayTokenRead.model_validate(token), plaintext=plaintext)

    async def list_tokens(self, user_id: int) -> list[GatewayToken]:
        return await self._repo.list_all(user_id=user_id)

    async def set_active(self, token_id: int, user_id: int, is_active: bool) -> GatewayToken:
        token = await self._repo.set_active(token_id, is_active, user_id=user_id)
        if not is_active:
            await self._forget(token.token_hash)
        return token

    async def delete_token(self, token_id: int, user_id: int) -> None:
        token_hash = (await self._repo.get(token_id, user_id=user_id)).token_hash
        await self._repo.delete(token_id, user_id=user_id)
        await self._forget(token_hash)

    async def authenticate(self, plaintext: str) -> int | None:
        token_hash = _hash_token(plaintext)

        if self._auth_cache is not None:
            cached_user_id = await self._auth_cache.get(token_hash)
            if cached_user_id is not None:
                return cached_user_id

        token = await self._repo.get_active_by_hash(token_hash)
        if token is None:
            return None

        if _is_stale(token.last_used_at):
            await self._repo.touch_last_used(token.id, stale_after=_LAST_USED_STALE_AFTER)
        if self._auth_cache is not None:
            await self._auth_cache.set(token_hash, token.user_id)
        return token.user_id

    async def _forget(self, token_hash: str) -> None:
        if self._auth_cache is not None:
            await self._auth_cache.delete(token_hash)
