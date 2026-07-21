from fastapi import APIRouter, Depends, status

from llm_gateway.admin.dependencies import require_admin
from llm_gateway.api.deps import get_gateway_token_service
from llm_gateway.tokens.schemas import GatewayTokenCreate, GatewayTokenCreated, GatewayTokenRead
from llm_gateway.tokens.service import GatewayTokenService

router = APIRouter(prefix="/admin/gateway-tokens", tags=["admin"], dependencies=[Depends(require_admin)])


@router.post("", response_model=GatewayTokenCreated, status_code=201)
async def create_token(
    payload: GatewayTokenCreate,
    service: GatewayTokenService = Depends(get_gateway_token_service),
) -> GatewayTokenCreated:
    """Generates a new gateway token. The plaintext is returned exactly

    once, here, and never again — the dashboard must show it to the admin
    immediately and cannot retrieve it later.
    """
    return await service.create_token(payload)


@router.get("", response_model=list[GatewayTokenRead])
async def list_tokens(
    service: GatewayTokenService = Depends(get_gateway_token_service),
) -> list[GatewayTokenRead]:
    tokens = await service.list_tokens()
    return [GatewayTokenRead.model_validate(t) for t in tokens]


@router.post("/{token_id}/revoke", response_model=GatewayTokenRead)
async def revoke_token(
    token_id: int,
    service: GatewayTokenService = Depends(get_gateway_token_service),
) -> GatewayTokenRead:
    token = await service.set_active(token_id, is_active=False)
    return GatewayTokenRead.model_validate(token)


@router.post("/{token_id}/activate", response_model=GatewayTokenRead)
async def activate_token(
    token_id: int,
    service: GatewayTokenService = Depends(get_gateway_token_service),
) -> GatewayTokenRead:
    token = await service.set_active(token_id, is_active=True)
    return GatewayTokenRead.model_validate(token)


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_token(
    token_id: int,
    service: GatewayTokenService = Depends(get_gateway_token_service),
) -> None:
    await service.delete_token(token_id)
