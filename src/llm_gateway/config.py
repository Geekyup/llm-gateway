from functools import lru_cache

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    APP_NAME: str = "llm-gateway"
    ENV: str = "local"
    DEBUG: bool = False

    # --- Database ---
    DATABASE_URL: PostgresDsn = Field(
        default="postgresql+asyncpg://llm_gateway:llm_gateway@localhost:5432/llm_gateway"
    )
    DB_ECHO: bool = False

    # --- Redis ---
    REDIS_URL: RedisDsn = Field(default="redis://localhost:6379/0")

    # --- Security ---
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    ENCRYPTION_KEY: str = Field(
        description="Fernet key used to encrypt API keys at rest. Required.",
    )
    ADMIN_API_KEY: str = Field(
        description="Static bearer token guarding the /admin/* endpoints in MVP.",
    )

    # --- Key pool behaviour ---
    KEY_STATUS_CACHE_TTL_SECONDS: int = 30
    GATEWAY_MAX_RETRY_ATTEMPTS: int = 3  # ceiling on failover hops per incoming request
    DEFAULT_DAILY_LIMIT: int = 1_000  # fallback if a key has no explicit daily_limit

    # --- Providers ---
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com"
    UPSTREAM_TIMEOUT_SECONDS: float = 60.0

    # --- ARQ / housekeeping ---
    HOUSEKEEPING_RESET_CRON_MINUTE: int = 0  # runs at minute 0 of every hour by default


@lru_cache
def get_settings() -> Settings:
    return Settings()
