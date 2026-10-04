from functools import lru_cache

from cryptography.fernet import Fernet
from pydantic import Field, PostgresDsn, RedisDsn, field_validator
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

    FRONTEND_URL: str = "http://localhost:5173"

    DATABASE_URL: PostgresDsn
    DB_ECHO: bool = False

    REDIS_URL: RedisDsn = "redis://localhost:6379/0"

    ENCRYPTION_KEY: str
    ADMIN_API_KEY: str = Field(min_length=32)
    JWT_SECRET_KEY: str = Field(min_length=32)
    SESSION_SECRET_KEY: str = Field(min_length=32)

    @field_validator("ENCRYPTION_KEY")
    @classmethod
    def _validate_encryption_key(cls, value: str) -> str:
        try:
            Fernet(value.encode())
        except ValueError as exc:
            raise ValueError("ENCRYPTION_KEY must be a valid Fernet key (32 url-safe base64-encoded bytes)") from exc
        return value

    KEY_STATUS_CACHE_TTL_SECONDS: int = 30
    GATEWAY_MAX_RETRY_ATTEMPTS: int = 3
    GATEWAY_RATE_LIMIT_PER_MINUTE: int = Field(default=120, ge=0)
    MAX_REQUEST_BODY_BYTES: int = Field(default=10 * 1024 * 1024, ge=1)
    DEFAULT_DAILY_LIMIT: int = 1_000

    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api"
    GROQ_BASE_URL: str = "https://api.groq.com/openai"
    UPSTREAM_TIMEOUT_SECONDS: float = 60.0
    DEFAULT_GEMINI_MODEL: str = "gemini-2.0-flash"
    DEFAULT_OPENROUTER_MODEL: str = "google/gemini-2.0-flash-001"
    DEFAULT_GROQ_MODEL: str = "llama-3.1-8b-instant"

    HOUSEKEEPING_RESET_CRON_MINUTE: int = 0
    HOUSEKEEPING_HEALTH_CHECK_CONCURRENCY: int = Field(default=3, ge=1)
    HOUSEKEEPING_HEALTH_CHECK_DELAY_SECONDS: float = Field(default=0.2, ge=0)
    HOUSEKEEPING_HEALTH_CHECK_TIMEOUT_SECONDS: int = Field(default=1500, ge=1)
    REQUEST_EVENTS_RETENTION_DAYS: int = Field(default=30, ge=1)

    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"


@lru_cache
def get_settings() -> Settings:
    return Settings()