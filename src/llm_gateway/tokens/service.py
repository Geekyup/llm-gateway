import hashlib
import logging
import secrets

from llm_gateway.tokens.models import GatewayToken
from llm_gateway.tokens.repository import GatewayTokenRepository
from llm_gateway.tokens.schemas import GatewayTokenCreate, GatewayTokenCreated, GatewayTokenRead

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

    async def create_token(self, payload: GatewayTokenCreate) -> GatewayTokenCreated:
        plaintext = f"{_TOKEN_PREFIX}_{secrets.token_urlsafe(_TOKEN_NBYTES)}"
        token = await self._repo.create(
            label=payload.label,
            token_hash=_hash_token(plaintext),
            token_preview=_preview(plaintext),
        )
        return GatewayTokenCreated(token=GatewayTokenRead.model_validate(token), plaintext=plaintext)

    async def list_tokens(self) -> list[GatewayToken]:
        return await self._repo.list_all()

    async def set_active(self, token_id: int, is_active: bool) -> GatewayToken:
        return await self._repo.set_active(token_id, is_active)

    async def delete_token(self, token_id: int) -> None:
        await self._repo.delete(token_id)

    async def verify(self, plaintext: str) -> bool:
        """Checks a bearer token against the pool of active gateway tokens.

        Used by the /v1/* proxy — never raises, just true/false, so a
        malformed or unknown token behaves the same as an invalid one.
        """
        token = await self._repo.get_by_hash(_hash_token(plaintext))
        if token is None or not token.is_active:
            return False
        await self._repo.touch_last_used(token.id)
        return True
