import json
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from app.api.deps import get_gateway_service
from app.gateway.attempts import UpstreamRequestSpec
from app.gateway.dependencies import require_gateway_token
from app.gateway.proxy_service import GatewayService
from app.gateway.schemas import GatewayErrorBody
from app.keys.enums import ProviderType
from app.keys.schemas import APIKeyDTO
from app.providers.registry import get_provider

router = APIRouter(prefix="/v1", tags=["gateway"])

_FORWARDED_HEADERS = frozenset({"accept"})

Gateway = Annotated[GatewayService, Depends(get_gateway_service)]
UserId = Annotated[int, Depends(require_gateway_token)]


class _RejectedRequest(Exception):
    def __init__(self, status_code: int, error: str, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.error = error
        self.detail = detail


def _resolve_provider(provider_name: str, method: str, path: str) -> ProviderType:
    try:
        provider_type = ProviderType(provider_name)
    except ValueError:
        raise _RejectedRequest(
            404, "unknown_provider", f"'{provider_name}' is not a supported provider"
        ) from None

    if not get_provider(provider_type.value).is_path_allowed(method, path):
        raise _RejectedRequest(
            404, "path_not_allowed", f"{method} /{path} is not exposed for '{provider_name}'"
        )
    return provider_type


async def _read_json_object(request: Request) -> dict | None:
    raw_body = await request.body()
    if not raw_body:
        return None
    try:
        decoded = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise _RejectedRequest(400, "invalid_json", "Request body is not valid JSON") from None
    if not isinstance(decoded, dict):
        raise _RejectedRequest(400, "invalid_json", "Request body must be a JSON object")
    return decoded


def _forwarded_headers(request: Request) -> dict[str, str]:
    return {k: v for k, v in request.headers.items() if k.lower() in _FORWARDED_HEADERS}


def _error_response(exc: _RejectedRequest, provider_name: str) -> JSONResponse:
    body = GatewayErrorBody(error=exc.error, provider=provider_name, detail=exc.detail)
    return JSONResponse(status_code=exc.status_code, content=body.model_dump())


async def _proxy(
    provider_name: str, path: str, request: Request, gateway: GatewayService, user_id: int
) -> Response:
    method = request.method
    try:
        provider_type = _resolve_provider(provider_name, method, path)
        payload = await _read_json_object(request)
    except _RejectedRequest as exc:
        return _error_response(exc, provider_name)

    spec = UpstreamRequestSpec(
        path=path, method=method, payload=payload, headers=_forwarded_headers(request)
    )

    def build_request(_key: APIKeyDTO) -> UpstreamRequestSpec:
        return spec

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
    provider_name: str, path: str, request: Request, gateway: Gateway, user_id: UserId
) -> Response:
    return await _proxy(provider_name, path, request, gateway, user_id)


@router.get("/{provider_name}/{path:path}", operation_id="proxy_gateway_request_get")
async def proxy_get(
    provider_name: str, path: str, request: Request, gateway: Gateway, user_id: UserId
) -> Response:
    return await _proxy(provider_name, path, request, gateway, user_id)
