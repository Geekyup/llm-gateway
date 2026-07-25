from fastapi import APIRouter, Depends, status

from app.api.deps import get_key_pool_service
from app.auth.deps import get_current_user
from app.auth.models import User
from app.keys.enums import ProviderType
from app.keys.schemas import APIKeyCreate, APIKeyHealthCheckResult, APIKeyRead, APIKeyUpdate
from app.keys.service import KeyPoolService

router = APIRouter(prefix="/me/keys", tags=["keys"])


@router.post("", response_model=APIKeyRead, status_code=201)
async def create_key(
    payload: APIKeyCreate,
    user: User = Depends(get_current_user),
    service: KeyPoolService = Depends(get_key_pool_service),
) -> APIKeyRead:
    key = await service.create_key(user.id, payload)
    return APIKeyRead.model_validate(key)


@router.get("", response_model=list[APIKeyRead])
async def list_keys(
    provider: ProviderType | None = None,
    user: User = Depends(get_current_user),
    service: KeyPoolService = Depends(get_key_pool_service),
) -> list[APIKeyRead]:
    keys = await service.list_keys(user.id, provider=provider)
    return [APIKeyRead.model_validate(key) for key in keys]


@router.patch("/{key_id}", response_model=APIKeyRead)
async def update_key(
    key_id: int,
    payload: APIKeyUpdate,
    user: User = Depends(get_current_user),
    service: KeyPoolService = Depends(get_key_pool_service),
) -> APIKeyRead:
    """Partial update — label, status, and/or daily_limit. Used for the

    dashboard's edit dialog and the enable/disable toggle. Scoped to the
    caller's own keys — a key_id belonging to another user behaves exactly
    like an unknown id (404), never a 403 that would confirm it exists.
    """
    key = await service.update_key(key_id, user.id, payload)
    return APIKeyRead.model_validate(key)


@router.post("/{key_id}/reset-cooldown", response_model=APIKeyRead)
async def reset_cooldown(
    key_id: int,
    user: User = Depends(get_current_user),
    service: KeyPoolService = Depends(get_key_pool_service),
) -> APIKeyRead:
    """Force a key back to ACTIVE and clear its cooldown timestamp early."""
    key = await service.reset_cooldown(key_id, user.id)
    return APIKeyRead.model_validate(key)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_key(
    key_id: int,
    user: User = Depends(get_current_user),
    service: KeyPoolService = Depends(get_key_pool_service),
) -> None:
    await service.delete_key(key_id, user.id)


@router.post("/{key_id}/check", response_model=APIKeyHealthCheckResult)
async def check_key(
    key_id: int,
    user: User = Depends(get_current_user),
    service: KeyPoolService = Depends(get_key_pool_service),
) -> APIKeyHealthCheckResult:
    """On-demand probe: makes a cheap upstream call with this key and updates
    its status based on the result (see KeyPoolService.check_key_health).
    """
    return await service.check_key_health(key_id, user.id)


@router.post("/check-all", response_model=list[APIKeyHealthCheckResult])
async def check_all_keys(
    provider: ProviderType | None = None,
    user: User = Depends(get_current_user),
    service: KeyPoolService = Depends(get_key_pool_service),
) -> list[APIKeyHealthCheckResult]:
    """Health-check every non-disabled key belonging to the caller (optionally scoped to one provider)."""
    return await service.check_all_keys(user.id, provider=provider)
