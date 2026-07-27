from fastapi import APIRouter, Depends, status

from app.api.deps import get_gateway_token_service
from app.auth.deps import get_current_user
from app.auth.models import User
from app.tokens.schemas import GatewayTokenCreate, GatewayTokenCreated, GatewayTokenRead
from app.tokens.service import GatewayTokenService

router = APIRouter(prefix="/me/gateway-tokens", tags=["gateway-tokens"])


@router.post("", response_model=GatewayTokenCreated, status_code=201)
async def create_token(
    payload: GatewayTokenCreate,
    user: User = Depends(get_current_user),
    service: GatewayTokenService = Depends(get_gateway_token_service),
) -> GatewayTokenCreated:
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
