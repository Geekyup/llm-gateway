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
