from fastapi import APIRouter, Depends, status

from llm_gateway.api.deps import get_gateway_token_service
from llm_gateway.auth.deps import get_current_user
from llm_gateway.auth.models import User
from llm_gateway.tokens.schemas import GatewayTokenCreate, GatewayTokenCreated, GatewayTokenRead
from llm_gateway.tokens.service import GatewayTokenService

router = APIRouter(prefix="/me/gateway-tokens", tags=["gateway-tokens"])


@router.post("", response_model=GatewayTokenCreated, status_code=201)
async def create_token(
    payload: GatewayTokenCreate,
    user: User = Depends(get_current_user),
    service: GatewayTokenService = Depends(get_gateway_token_service),
) -> GatewayTokenCreated:
    """Generates a new gateway token owned by the caller. The plaintext is

    returned exactly once, here, and never again — the dashboard must show
    it to the user immediately and cannot retrieve it later. A token
    minted this way can only ever draw on its owner's own key pool.
    """
    return await service.create_token(user.id, payload)


@router.get("", response_model=list[GatewayTokenRead])
async def list_tokens(
    user: User = Depends(get_current_user),
    service: GatewayTokenService = Depends(get_gateway_token_service),
) -> list[GatewayTokenRead]:
    tokens = await service.list_tokens(user.id)
    return [GatewayTokenRead.model_validate(t) for t in tokens]


@router.post("/{token_id}/revoke", response_model=GatewayTokenRead)
async def revoke_token(
    token_id: int,
    user: User = Depends(get_current_user),
    service: GatewayTokenService = Depends(get_gateway_token_service),
) -> GatewayTokenRead:
    token = await service.set_active(token_id, user.id, is_active=False)
    return GatewayTokenRead.model_validate(token)


@router.post("/{token_id}/activate", response_model=GatewayTokenRead)
async def activate_token(
    token_id: int,
    user: User = Depends(get_current_user),
    service: GatewayTokenService = Depends(get_gateway_token_service),
) -> GatewayTokenRead:
    token = await service.set_active(token_id, user.id, is_active=True)
    return GatewayTokenRead.model_validate(token)


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_token(
    token_id: int,
    user: User = Depends(get_current_user),
    service: GatewayTokenService = Depends(get_gateway_token_service),
) -> None:
    await service.delete_token(token_id, user.id)
