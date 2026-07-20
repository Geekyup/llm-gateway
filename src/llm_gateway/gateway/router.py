from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from llm_gateway.api.deps import get_gateway_service
from llm_gateway.core.exceptions import NoAvailableKeysError, ProviderNotSupportedError, UpstreamExhaustedError
from llm_gateway.gateway.proxy_service import GatewayService
from llm_gateway.gateway.schemas import GatewayErrorBody
from llm_gateway.keys.enums import ProviderType
from llm_gateway.providers.registry import get_provider

router = APIRouter(prefix="/v1", tags=["gateway"])


async def _proxy_impl(
    provider_name: str,
    path: str,
    request: Request,
    gateway: GatewayService = Depends(get_gateway_service),
) -> Response:
    """Transparent proxy: POST /v1/gemini/v1beta/models/gemini-1.5-flash:generateContent

    Client never sees which underlying API key served the request, nor
    that a 429 caused a silent retry against a different key.
    """
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

    try:
        upstream_response = await gateway.proxy_request(
            provider=provider,
            provider_type=provider_type,
            path=path,
            method=request.method,
            payload=payload,
            headers=dict(request.headers),
        )
    except NoAvailableKeysError as exc:
        return JSONResponse(
            status_code=503,
            content=GatewayErrorBody(error="no_available_keys", provider=provider_name, detail=str(exc)).model_dump(),
        )
    except UpstreamExhaustedError as exc:
        return JSONResponse(
            status_code=503,
            content=GatewayErrorBody(error="upstream_exhausted", provider=provider_name, detail=str(exc)).model_dump(),
        )
    except ProviderNotSupportedError as exc:
        return JSONResponse(
            status_code=404,
            content=GatewayErrorBody(error="provider_not_supported", provider=provider_name, detail=str(exc)).model_dump(),
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
) -> Response:
    return await _proxy_impl(provider_name, path, request, gateway)


@router.get("/{provider_name}/{path:path}", operation_id="proxy_gateway_request_get")
async def proxy_get(
    provider_name: str,
    path: str,
    request: Request,
    gateway: GatewayService = Depends(get_gateway_service),
) -> Response:
    return await _proxy_impl(provider_name, path, request, gateway)
