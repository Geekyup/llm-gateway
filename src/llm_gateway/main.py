from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from llm_gateway.admin.gateway_tokens_router import router as gateway_tokens_router
from llm_gateway.admin.router import router as admin_router
from llm_gateway.config import get_settings
from llm_gateway.core.logging import configure_logging
from llm_gateway.gateway.router import router as gateway_router
from llm_gateway.monitoring.router import router as monitoring_router
from llm_gateway.openai_compat.router import router as openai_compat_router


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

    # openai_compat_router must be registered before gateway_router: FastAPI
    # matches routes in registration order, and gateway_router's catch-all
    # POST /v1/{provider_name}/{path:path} would otherwise swallow
    # POST /v1/chat/completions (provider_name="chat", path="completions").
    app.include_router(openai_compat_router)
    app.include_router(gateway_router)
    app.include_router(admin_router)
    app.include_router(gateway_tokens_router)
    app.include_router(monitoring_router)

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
