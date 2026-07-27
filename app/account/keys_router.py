from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from app.api.deps import get_event_publisher, get_key_pool_service
from app.auth.deps import get_current_user
from app.auth.models import User
from app.keys.enums import ProviderType
from app.keys.schemas import APIKeyCreate, APIKeyHealthCheckResult, APIKeyRead, APIKeyUpdate
from app.keys.service import KeyPoolService
from app.monitoring.publisher import RequestEventPublisher
from app.monitoring.schemas import (
    HourlyTokenPoint,
    HourlyTokenUsageResponse,
    HourlyUsagePoint,
    HourlyUsageResponse,
)
from app.providers.registry import get_provider

router = APIRouter(prefix="/me/keys", tags=["keys"])


class ListModelsRequest(BaseModel):
    provider: ProviderType
    raw_key: str = Field(..., description="Plaintext API key, tried live against the provider. Never stored.")


class ModelOption(BaseModel):
    id: str
    label: str


class ListModelsResponse(BaseModel):
    models: list[ModelOption]


@router.post("", response_model=APIKeyRead, status_code=201)
async def create_key(
    payload: APIKeyCreate,
    user: User = Depends(get_current_user),
    service: KeyPoolService = Depends(get_key_pool_service),
) -> APIKeyRead:
    key = await service.create_key(user.id, payload)
    return APIKeyRead.model_validate(key)


@router.post("/list-models", response_model=ListModelsResponse)
async def list_models(
    payload: ListModelsRequest,
    user: User = Depends(get_current_user),
) -> ListModelsResponse:
    """Live model catalog for a not-yet-saved key, for the Add/Edit Key
    form's model picker. Tries `payload.raw_key` directly against the
    provider — the key is never persisted or logged here, only used for
    this one on-demand call (same trust boundary as the Test Key health
    check). Raises 502 (via ProviderRequestError) if the key is invalid or
    the provider call fails, so the form can show why nothing came back
    instead of just an empty picker.
    """
    provider = get_provider(payload.provider.value)
    models = await provider.list_models(payload.raw_key)
    return ListModelsResponse(models=[ModelOption(id=m.id, label=m.label) for m in models])


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


@router.get("/{key_id}/hourly-usage", response_model=HourlyUsageResponse)
async def hourly_usage(
    key_id: int,
    user: User = Depends(get_current_user),
    service: KeyPoolService = Depends(get_key_pool_service),
    publisher: RequestEventPublisher = Depends(get_event_publisher),
) -> HourlyUsageResponse:
    """Real per-hour request counts for this key, for the current UTC day.

    Derived from the live-monitor's Redis event history rather than a
    separate table, so coverage is bounded by that history's capped size —
    see RequestEventPublisher.hourly_usage_for_key for the exact caveat.
    Raises 404 (via KeyNotFoundError) if key_id doesn't belong to the
    caller, same as every other per-key endpoint here.
    """
    await service.get_key(key_id, user.id)
    counts = await publisher.hourly_usage_for_key(user.id, key_id)
    points = [HourlyUsagePoint(hour=h, requests=c) for h, c in enumerate(counts)]
    return HourlyUsageResponse(key_id=key_id, points=points)


@router.get("/{key_id}/hourly-token-usage", response_model=HourlyTokenUsageResponse)
async def hourly_token_usage(
    key_id: int,
    user: User = Depends(get_current_user),
    service: KeyPoolService = Depends(get_key_pool_service),
    publisher: RequestEventPublisher = Depends(get_event_publisher),
) -> HourlyTokenUsageResponse:
    """Real per-hour token counts (prompt/completion/total) for this key,
    for the current UTC day. Same Redis-history source and coverage caveat
    as /hourly-usage — see RequestEventPublisher.hourly_token_usage_for_key.
    Only successful requests carry token counts.
    """
    await service.get_key(key_id, user.id)
    triples = await publisher.hourly_token_usage_for_key(user.id, key_id)
    points = [
        HourlyTokenPoint(hour=h, prompt_tokens=p, completion_tokens=c, total_tokens=t)
        for h, (p, c, t) in enumerate(triples)
    ]
    return HourlyTokenUsageResponse(key_id=key_id, points=points)
