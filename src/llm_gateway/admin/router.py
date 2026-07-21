from fastapi import APIRouter, Depends, status

from llm_gateway.admin.dependencies import require_admin
from llm_gateway.api.deps import get_key_pool_service
from llm_gateway.keys.enums import ProviderType
from llm_gateway.keys.schemas import APIKeyCreate, APIKeyRead, APIKeyUpdate
from llm_gateway.keys.service import KeyPoolService

router = APIRouter(prefix="/admin/keys", tags=["admin"], dependencies=[Depends(require_admin)])


@router.post("", response_model=APIKeyRead, status_code=201)
async def create_key(
    payload: APIKeyCreate,
    service: KeyPoolService = Depends(get_key_pool_service),
) -> APIKeyRead:
    key = await service.create_key(payload)
    return APIKeyRead.model_validate(key)


@router.get("", response_model=list[APIKeyRead])
async def list_keys(
    provider: ProviderType | None = None,
    service: KeyPoolService = Depends(get_key_pool_service),
) -> list[APIKeyRead]:
    keys = await service.list_keys(provider=provider)
    return [APIKeyRead.model_validate(key) for key in keys]


@router.patch("/{key_id}", response_model=APIKeyRead)
async def update_key(
    key_id: int,
    payload: APIKeyUpdate,
    service: KeyPoolService = Depends(get_key_pool_service),
) -> APIKeyRead:
    """Partial update — label, status, and/or daily_limit. Used for the

    dashboard's edit dialog and the enable/disable toggle.
    """
    key = await service.update_key(key_id, payload)
    return APIKeyRead.model_validate(key)


@router.post("/{key_id}/reset-cooldown", response_model=APIKeyRead)
async def reset_cooldown(
    key_id: int,
    service: KeyPoolService = Depends(get_key_pool_service),
) -> APIKeyRead:
    """Force a key back to ACTIVE and clear its cooldown timestamp early."""
    key = await service.reset_cooldown(key_id)
    return APIKeyRead.model_validate(key)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_key(
    key_id: int,
    service: KeyPoolService = Depends(get_key_pool_service),
) -> None:
    await service.delete_key(key_id)
