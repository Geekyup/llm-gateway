import hashlib
import logging
import secrets

from app.tokens.models import GatewayToken
from app.tokens.repository import GatewayTokenRepository
from app.tokens.schemas import GatewayTokenCreate, GatewayTokenCreated, GatewayTokenRead

logger = logging.getLogger(__name__)

_TOKEN_PREFIX = "gwk"  # "gateway key" — lets tokens be recognized at a glance, à la sk-/gh_p_ etc.
_TOKEN_NBYTES = 32  # 256 bits of entropy


def _hash_token(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode()).hexdigest()


def _preview(plaintext: str) -> str:
    # e.g. "gwk_ab12...wxyz" — enough to recognize, not enough to guess anything.
    return f"{plaintext[:7]}...{plaintext[-4:]}"


class GatewayTokenService:
    """Public API for issuing and verifying client-facing gateway tokens.

    Separate from KeyPoolService (which manages upstream provider keys):
    this is the *inbound* side — who is allowed to call the gateway at all,
    as opposed to which upstream key the gateway uses on their behalf.
    """

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
        """Resolves a bearer token to its owning user_id, or None if invalid.

        Used by the /v1/* proxy: this is the only place a GatewayToken's
        raw value ever gets checked, and the returned user_id is what
        scopes every downstream key-pool lookup for that request — so a
        token minted for one account can never draw on another account's
        keys, regardless of what provider/path it's used against.
        """
        token = await self._repo.get_by_hash(_hash_token(plaintext))
        if token is None or not token.is_active:
            return None
        await self._repo.touch_last_used(token.id)
        return token.user_id
