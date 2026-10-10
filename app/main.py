from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from app.account.gateway_tokens_router import router as gateway_tokens_router
from app.account.keys_router import router as keys_router
from app.account.playground_router import router as playground_router
from app.auth.router import router as auth_router
from app.config import get_settings
from app.core.body_limit import BodySizeLimitMiddleware
from app.core.exceptions import LLMGatewayError
from app.core.logging import configure_logging
from app.core.middleware import REQUEST_ID_HEADER, RequestContextMiddleware
from app.core.system_router import router as system_router
from app.db.redis import get_redis_pool
from app.db.session import get_engine
from app.gateway.router import router as gateway_router
from app.gateway.schemas import GatewayErrorBody
from app.monitoring.activity_router import router as activity_router
from app.openai_compat.router import router as openai_compat_router
from app.providers.registry import close_shared_client

settings = get_settings()
configure_logging(debug=settings.DEBUG, fmt=settings.LOG_FORMAT)

@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await close_shared_client()
    await get_redis_pool().disconnect()
    await get_engine().dispose()


_is_prod = settings.ENV == "production"

app = FastAPI(
    lifespan=lifespan,
    docs_url=None if _is_prod else "/docs",
    redoc_url=None if _is_prod else "/redoc",
    openapi_url=None if _is_prod else "/openapi.json",
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
    expose_headers=[REQUEST_ID_HEADER],
)
app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.MAX_REQUEST_BODY_BYTES)
app.add_middleware(SessionMiddleware, secret_key=settings.SESSION_SECRET_KEY, same_site="lax")
app.add_middleware(RequestContextMiddleware)


@app.exception_handler(LLMGatewayError)
async def llm_gateway_error_handler(request: Request, exc: LLMGatewayError) -> JSONResponse:
    if exc.slug is None:
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})

    provider = getattr(exc, "provider", "unknown")
    body = GatewayErrorBody(error=exc.slug, provider=provider, detail=str(exc))
    return JSONResponse(status_code=exc.status_code, content=body.model_dump())


app.include_router(system_router)
app.include_router(openai_compat_router)
app.include_router(gateway_router)
app.include_router(keys_router)
app.include_router(gateway_tokens_router)
app.include_router(playground_router)
app.include_router(activity_router)
app.include_router(auth_router)
