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

    # --- CORS ---
    # Comma-separated list of allowed origins for the admin frontend, e.g.
    # "http://localhost:5173,https://admin.example.com"
    CORS_ORIGINS_RAW: str = Field(default="http://localhost:5173", alias="CORS_ORIGINS")

    @property
    def CORS_ORIGINS(self) -> list[str]:  # noqa: N802
        return [origin.strip() for origin in self.CORS_ORIGINS_RAW.split(",") if origin.strip()]

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

    # --- Auth (Google-only login) ---
    JWT_SECRET_KEY: str = Field(
        description="Signing key for access/refresh JWTs. Required, keep separate from ENCRYPTION_KEY.",
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    GOOGLE_CLIENT_ID: str = Field(default="", description="OAuth client ID from Google Cloud Console.")
    GOOGLE_CLIENT_SECRET: str = Field(default="", description="OAuth client secret from Google Cloud Console.")
    GOOGLE_REDIRECT_URI: str = Field(
        default="http://localhost:8000/auth/google/callback",
        description="Must exactly match a redirect URI registered in the Google OAuth client.",
    )
    # Signs the short-lived state/session cookie used only to carry the
    # OAuth nonce between /login and /callback — unrelated to JWT_SECRET_KEY.
    SESSION_SECRET_KEY: str = Field(description="Signing key for the OAuth state cookie. Required.")


@lru_cache
def get_settings() -> Settings:
    return Settings()
