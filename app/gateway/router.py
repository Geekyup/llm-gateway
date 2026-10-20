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
from app.providers.registry import get_provider

router = APIRouter(prefix="/v1", tags=["gateway"])

_FORWARDED_HEADERS = frozenset({"accept"})

Gateway = Annotated[GatewayService, Depends(get_gateway_service)]
UserId = Annotated[int, Depends(require_gateway_token)]


def _reject(status_code: int, error: str, provider_name: str, detail: str) -> JSONResponse:
    body = GatewayErrorBody(error=error, provider=provider_name, detail=detail)
    return JSONResponse(status_code=status_code, content=body.model_dump())


async def _proxy(
    provider_name: str, path: str, request: Request, gateway: GatewayService, user_id: int
) -> Response:
    method = request.method

    try:
        provider_type = ProviderType(provider_name)
    except ValueError:
        return _reject(
            404, "unknown_provider", provider_name, f"'{provider_name}' is not a supported provider"
        )

    if not get_provider(provider_type.value).is_path_allowed(method, path):
        return _reject(
            404,
            "path_not_allowed",
            provider_name,
            f"{method} /{path} is not exposed for '{provider_name}'",
        )

    payload = None
    raw_body = await request.body()
    if raw_body:
        try:
            payload = json.loads(raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return _reject(400, "invalid_json", provider_name, "Request body is not valid JSON")
        if not isinstance(payload, dict):
            return _reject(
                400, "invalid_json", provider_name, "Request body must be a JSON object"
            )

    spec = UpstreamRequestSpec(
        path=path,
        method=method,
        payload=payload,
        headers={k: v for k, v in request.headers.items() if k.lower() in _FORWARDED_HEADERS},
    )
    upstream_response, _ = await gateway.proxy_request(
        user_id=user_id,
        build_request=lambda _key: spec,
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
