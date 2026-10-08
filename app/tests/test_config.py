import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError

from app.config import Settings

_VALID = {
    "DATABASE_URL": "postgresql+asyncpg://u:p@localhost/db",
    "ENCRYPTION_KEY": Fernet.generate_key().decode(),
    "ADMIN_API_KEY": "a" * 32,
    "JWT_SECRET_KEY": "j" * 32,
    "SESSION_SECRET_KEY": "s" * 32,
}


def _build(**overrides) -> Settings:
    return Settings(_env_file=None, **{**_VALID, **overrides})


def test_valid_settings_load():
    assert _build().JWT_SECRET_KEY == "j" * 32


@pytest.mark.parametrize("field", ["ADMIN_API_KEY", "JWT_SECRET_KEY", "SESSION_SECRET_KEY"])
def test_short_secrets_are_rejected(field):
    with pytest.raises(ValidationError):
        _build(**{field: "short"})


def test_invalid_fernet_key_is_rejected():
    with pytest.raises(ValidationError):
        _build(ENCRYPTION_KEY="not-a-fernet-key")


def test_database_url_has_no_default_credentials(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    values = {k: v for k, v in _VALID.items() if k != "DATABASE_URL"}

    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


def test_observability_defaults():
    settings = _build()

    assert settings.LOG_FORMAT == "text"
    assert settings.METRICS_TOKEN == ""
    assert settings.READINESS_TIMEOUT_SECONDS == 2.0
    assert settings.ACTIVITY_CACHE_TTL_SECONDS == 30


def test_log_format_only_accepts_text_or_json():
    assert _build(LOG_FORMAT="json").LOG_FORMAT == "json"
    with pytest.raises(ValidationError):
        _build(LOG_FORMAT="xml")


def test_cache_ttl_can_be_zero_but_not_negative():
    assert _build(ACTIVITY_CACHE_TTL_SECONDS=0).ACTIVITY_CACHE_TTL_SECONDS == 0
    with pytest.raises(ValidationError):
        _build(ACTIVITY_CACHE_TTL_SECONDS=-1)


def test_readiness_timeout_must_be_positive():
    with pytest.raises(ValidationError):
        _build(READINESS_TIMEOUT_SECONDS=0)
