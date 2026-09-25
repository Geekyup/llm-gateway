import pytest
from pydantic import ValidationError

from app.config import Settings


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_housekeeping_defaults():
    settings = _settings()

    assert settings.HOUSEKEEPING_RESET_CRON_MINUTE == 0
    assert settings.HOUSEKEEPING_HEALTH_CHECK_CONCURRENCY == 3
    assert settings.HOUSEKEEPING_HEALTH_CHECK_DELAY_SECONDS == 0.2
    assert settings.HOUSEKEEPING_HEALTH_CHECK_TIMEOUT_SECONDS == 1500
    assert settings.REQUEST_EVENTS_RETENTION_DAYS == 30


def test_housekeeping_values_are_read_from_env(monkeypatch):
    monkeypatch.setenv("HOUSEKEEPING_HEALTH_CHECK_CONCURRENCY", "8")
    monkeypatch.setenv("REQUEST_EVENTS_RETENTION_DAYS", "90")

    settings = _settings()

    assert settings.HOUSEKEEPING_HEALTH_CHECK_CONCURRENCY == 8
    assert settings.REQUEST_EVENTS_RETENTION_DAYS == 90


@pytest.mark.parametrize(
    "name",
    [
        "HOUSEKEEPING_HEALTH_CHECK_CONCURRENCY",
        "HOUSEKEEPING_HEALTH_CHECK_TIMEOUT_SECONDS",
        "REQUEST_EVENTS_RETENTION_DAYS",
    ],
)
def test_zero_is_rejected_where_it_would_break_the_job(name):
    with pytest.raises(ValidationError):
        _settings(**{name: 0})
