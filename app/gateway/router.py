from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from app.api.deps import get_gateway_service
from app.gateway.dependencies import require_gateway_token
from app.gateway.proxy_service import GatewayService
from app.gateway.schemas import GatewayErrorBody
from app.keys.enums import ProviderType
from app.providers.registry import get_provider

router = APIRouter(prefix="/v1", tags=["gateway"])


async def _proxy_impl(
    provider_name: str,
    path: str,
    request: Request,
    gateway: GatewayService,
    user_id: int,
) -> Response:
    try:
        provider_type = ProviderType(provider_name)
    except ValueError:
        return JSONResponse(
            status_code=404,
            content=GatewayErrorBody(
                error="unknown_provider", provider=provider_name, detail=f"'{provider_name}' is not a supported provider"
            ).model_dump(),
        )

    provider = get_provider(provider_type.value)
    payload = await request.json() if await request.body() else None

    upstream_response = await gateway.proxy_request(
        user_id=user_id,
        provider=provider,
        provider_type=provider_type,
        path=path,
        method=request.method,
        payload=payload,
        headers=dict(request.headers),
    )

    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        media_type=upstream_response.headers.get("content-type", "application/json"),
    )


@router.post("/{provider_name}/{path:path}", operation_id="proxy_gateway_request_post")
async def proxy_post(
    provider_name: str,
    path: str,
    request: Request,
    gateway: GatewayService = Depends(get_gateway_service),
    user_id: int = Depends(require_gateway_token),
) -> Response:
    return await _proxy_impl(provider_name, path, request, gateway, user_id)


@router.get("/{provider_name}/{path:path}", operation_id="proxy_gateway_request_get")
async def proxy_get(
    provider_name: str,
    path: str,
    request: Request,
    gateway: GatewayService = Depends(get_gateway_service),
    user_id: int = Depends(require_gateway_token),
) -> Response:
    return await _proxy_impl(provider_name, path, request, gateway, user_id)
