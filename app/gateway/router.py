import json

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from app.api.deps import get_gateway_service
from app.gateway.dependencies import require_gateway_token
from app.gateway.proxy_service import GatewayService, UpstreamRequestSpec
from app.gateway.schemas import GatewayErrorBody
from app.keys.enums import ProviderType
from app.keys.schemas import APIKeyDTO
from app.providers.registry import get_provider

router = APIRouter(prefix="/v1", tags=["gateway"])

_FORWARDED_HEADERS = frozenset({"accept"})


def _error(status_code: int, error: str, provider: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=GatewayErrorBody(error=error, provider=provider, detail=detail).model_dump(),
    )


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
        return _error(404, "unknown_provider", provider_name, f"'{provider_name}' is not a supported provider")

    method = request.method
    if not get_provider(provider_type.value).is_path_allowed(method, path):
        return _error(
            404, "path_not_allowed", provider_name, f"{method} /{path} is not exposed for '{provider_name}'"
        )

    raw_body = await request.body()
    payload: dict | None = None
    if raw_body:
        try:
            decoded = json.loads(raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return _error(400, "invalid_json", provider_name, "Request body is not valid JSON")
        if not isinstance(decoded, dict):
            return _error(400, "invalid_json", provider_name, "Request body must be a JSON object")
        payload = decoded

    headers = {k: v for k, v in request.headers.items() if k.lower() in _FORWARDED_HEADERS}

    def build_request(_dto: APIKeyDTO) -> UpstreamRequestSpec:
        return UpstreamRequestSpec(path=path, method=method, payload=payload, headers=headers)

    upstream_response, _ = await gateway.proxy_request(
        user_id=user_id,
        build_request=build_request,
        provider_type=provider_type,
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
