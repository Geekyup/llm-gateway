import hashlib
import logging
import secrets

from app.tokens.models import GatewayToken
from app.tokens.repository import GatewayTokenRepository
from app.tokens.schemas import GatewayTokenCreate, GatewayTokenCreated, GatewayTokenRead

logger = logging.getLogger(__name__)

_TOKEN_PREFIX = "gwk"  
_TOKEN_NBYTES = 32  


def _hash_token(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode()).hexdigest()


def _preview(plaintext: str) -> str:
    return f"{plaintext[:7]}...{plaintext[-4:]}"


class GatewayTokenService:
    def __init__(self, repository: GatewayTokenRepository) -> None:
        self._repo = repository

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
        return await self._repo.set_active(token_id, is_active, user_id=user_id)

    async def delete_token(self, token_id: int, user_id: int) -> None:
        await self._repo.delete(token_id, user_id=user_id)

    async def authenticate(self, plaintext: str) -> int | None:
        token = await self._repo.get_by_hash(_hash_token(plaintext))
        if token is None or not token.is_active:
            return None
        await self._repo.touch_last_used(token.id)
        return token.user_id
