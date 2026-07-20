from fastapi import APIRouter, Depends

from llm_gateway.admin.dependencies import require_admin
from llm_gateway.api.deps import get_key_pool_service
from llm_gateway.keys.enums import ProviderType
from llm_gateway.keys.schemas import APIKeyCreate, APIKeyRead
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
