from fastapi import FastAPI

from llm_gateway.admin.router import router as admin_router
from llm_gateway.config import get_settings
from llm_gateway.core.logging import configure_logging
from llm_gateway.gateway.router import router as gateway_router


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(debug=settings.DEBUG)

    app = FastAPI(
        title=settings.APP_NAME,
        description="Gateway API with a rotating pool of Gemini API keys and automatic 429 failover.",
        version="0.1.0",
    )

    app.include_router(gateway_router)
    app.include_router(admin_router)

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
