from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from app.account.gateway_tokens_router import router as gateway_tokens_router
from app.account.keys_router import router as keys_router
from app.account.playground_router import router as playground_router
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
        description=(
            "Gateway API with a rotating pool of API keys across multiple providers "
            "(Gemini, Groq, OpenRouter) and automatic failover on rate limits/exhaustion."
        ),
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SessionMiddleware, secret_key=settings.SESSION_SECRET_KEY, same_site="lax")

    @app.exception_handler(LLMGatewayError)
    async def llm_gateway_error_handler(request: Request, exc: LLMGatewayError) -> JSONResponse:
        if request.url.path.startswith("/v1/") and type(exc) in _GATEWAY_ERROR_SLUGS:
            provider = getattr(exc, "provider", "unknown")
            body = GatewayErrorBody(
                error=_GATEWAY_ERROR_SLUGS[type(exc)], provider=provider, detail=str(exc)
            )
            return JSONResponse(status_code=exc.status_code, content=body.model_dump())

        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})

    app.include_router(openai_compat_router)
    app.include_router(gateway_router)
    app.include_router(keys_router)
    app.include_router(gateway_tokens_router)
    app.include_router(playground_router)
    app.include_router(monitoring_router)
    app.include_router(auth_router)

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}
    return app


app = create_app()
