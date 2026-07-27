from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from app.admin.gateway_tokens_router import router as gateway_tokens_router
from app.admin.router import router as admin_router
from app.auth.router import router as auth_router
from app.config import get_settings
from app.core.exceptions import (
    LLMGatewayError,
    NoAvailableKeysError,
    ProviderNotSupportedError,
    UpstreamExhaustedError,
)
from app.core.logging import configure_logging
from app.gateway.router import router as gateway_router
from app.gateway.schemas import GatewayErrorBody
from app.monitoring.router import router as monitoring_router
from app.openai_compat.router import router as openai_compat_router

# Maps a domain exception to the "error" slug the gateway's public JSON
# error body uses. Only exceptions the /v1/* proxy path can actually raise
# need an entry here — anything else falls through to the generic
# {"detail": ...} handler below.
_GATEWAY_ERROR_SLUGS: dict[type[LLMGatewayError], str] = {
    NoAvailableKeysError: "no_available_keys",
    UpstreamExhaustedError: "upstream_exhausted",
    ProviderNotSupportedError: "provider_not_supported",
}


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(debug=settings.DEBUG)

    app = FastAPI(
        title=settings.APP_NAME,
        description="Gateway API with a rotating pool of Gemini API keys and automatic 429 failover.",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Only used to carry the OAuth nonce between /auth/google/login and
    # /auth/google/callback — unrelated to the access/refresh JWTs issued
    # after login, which are stateless and never touch this cookie.
    app.add_middleware(SessionMiddleware, secret_key=settings.SESSION_SECRET_KEY, same_site="lax")

    @app.exception_handler(LLMGatewayError)
    async def llm_gateway_error_handler(request: Request, exc: LLMGatewayError) -> JSONResponse:
        """Single seam for every domain exception in app.core.exceptions.

        Routers raise these directly instead of each wrapping calls in
        their own try/except HTTPException block. The /v1/{provider}/...
        proxy path is the one exception: its public contract is the
        {error, provider, detail} shape (GatewayErrorBody), which existing
        client integrations already depend on, so it's preserved here
        rather than folded into the generic {"detail": ...} body below.
        """
        if request.url.path.startswith("/v1/") and type(exc) in _GATEWAY_ERROR_SLUGS:
            provider = getattr(exc, "provider", "unknown")
            body = GatewayErrorBody(
                error=_GATEWAY_ERROR_SLUGS[type(exc)], provider=provider, detail=str(exc)
            )
            return JSONResponse(status_code=exc.status_code, content=body.model_dump())

        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})

    # openai_compat_router must be registered before gateway_router: FastAPI
    # matches routes in registration order, and gateway_router's catch-all
    # POST /v1/{provider_name}/{path:path} would otherwise swallow
    # POST /v1/chat/completions (provider_name="chat", path="completions").
    app.include_router(openai_compat_router)
    app.include_router(gateway_router)
    app.include_router(admin_router)
    app.include_router(gateway_tokens_router)
    app.include_router(monitoring_router)
    app.include_router(auth_router)

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
