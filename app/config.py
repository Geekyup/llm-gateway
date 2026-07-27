from functools import lru_cache

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "llm-gateway"
    ENV: str = "local"
    DEBUG: bool = False

    CORS_ORIGINS_RAW: str = Field(default="http://localhost:5173", alias="CORS_ORIGINS")

    @property
    def CORS_ORIGINS(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS_RAW.split(",") if origin.strip()]

    DATABASE_URL: PostgresDsn = "postgresql+asyncpg://llm_gateway:llm_gateway@localhost:5432/llm_gateway"
    DB_ECHO: bool = False

    REDIS_URL: RedisDsn = "redis://localhost:6379/0"

    ENCRYPTION_KEY: str
    ADMIN_API_KEY: str
    JWT_SECRET_KEY: str
    SESSION_SECRET_KEY: str

    KEY_STATUS_CACHE_TTL_SECONDS: int = 30
    GATEWAY_MAX_RETRY_ATTEMPTS: int = 3
    DEFAULT_DAILY_LIMIT: int = 1_000

    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api"
    UPSTREAM_TIMEOUT_SECONDS: float = 60.0

    HOUSEKEEPING_RESET_CRON_MINUTE: int = 0

    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"


@lru_cache
def get_settings() -> Settings:
    return Settings()