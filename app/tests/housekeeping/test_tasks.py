import logging
from contextlib import asynccontextmanager
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.housekeeping import tasks
from app.keys.enums import KeyStatus
from app.keys.schemas import APIKeyHealthCheckResult


def _patch_service(service):
    @asynccontextmanager
    async def fake_key_pool_service():
        yield service

    return patch.object(tasks, "_key_pool_service", fake_key_pool_service)


def _patch_settings(**overrides):
    values = {
        "HOUSEKEEPING_HEALTH_CHECK_CONCURRENCY": 3,
        "HOUSEKEEPING_HEALTH_CHECK_DELAY_SECONDS": 0.2,
        "REQUEST_EVENTS_RETENTION_DAYS": 30,
    }
    values.update(overrides)
    return patch.object(tasks, "get_settings", return_value=MagicMock(**values))


def _patch_sessionmaker():
    session = MagicMock()
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=None)
    factory = MagicMock(return_value=session_cm)
    return patch.object(tasks, "get_sessionmaker", return_value=factory), session


@pytest.mark.asyncio
async def test_clear_expired_cooldowns_logs_when_keys_revived(caplog):
    service = AsyncMock()
    service.clear_expired_cooldowns.return_value = [object(), object()]

    with _patch_service(service), caplog.at_level(logging.INFO, logger=tasks.logger.name):
        await tasks.clear_expired_cooldowns({})

    service.clear_expired_cooldowns.assert_awaited_once()
    assert "revived 2 key(s)" in caplog.text


@pytest.mark.asyncio
async def test_clear_expired_cooldowns_is_silent_when_nothing_revived(caplog):
    service = AsyncMock()
    service.clear_expired_cooldowns.return_value = []

    with _patch_service(service), caplog.at_level(logging.INFO, logger=tasks.logger.name):
        await tasks.clear_expired_cooldowns({})

    assert caplog.text == ""


@pytest.mark.asyncio
async def test_reset_daily_limits_logs_count(caplog):
    service = AsyncMock()
    service.reset_daily_counters.return_value = [object()] * 4

    with _patch_service(service), caplog.at_level(logging.INFO, logger=tasks.logger.name):
        await tasks.reset_daily_limits({})

    service.reset_daily_counters.assert_awaited_once()
    assert "reset 4 key(s)" in caplog.text


@pytest.mark.asyncio
async def test_reset_daily_limits_logs_zero_when_nothing_to_reset(caplog):
    service = AsyncMock()
    service.reset_daily_counters.return_value = []

    with _patch_service(service), caplog.at_level(logging.INFO, logger=tasks.logger.name):
        await tasks.reset_daily_limits({})

    assert "reset 0 key(s)" in caplog.text


@pytest.mark.asyncio
async def test_health_check_exhausted_keys_filters_by_status_in_query(caplog):
    service = AsyncMock()
    service.list_all_keys_system_wide.return_value = []
    service.check_keys.return_value = []

    with _patch_service(service), _patch_settings():
        await tasks.health_check_exhausted_keys({})

    service.list_all_keys_system_wide.assert_awaited_once_with(status=KeyStatus.EXHAUSTED)


@pytest.mark.asyncio
async def test_health_check_exhausted_keys_passes_limits_from_settings():
    exhausted = [object(), object()]
    service = AsyncMock()
    service.list_all_keys_system_wide.return_value = exhausted
    service.check_keys.return_value = []

    with _patch_service(service), _patch_settings(
        HOUSEKEEPING_HEALTH_CHECK_CONCURRENCY=5,
        HOUSEKEEPING_HEALTH_CHECK_DELAY_SECONDS=1.5,
    ):
        await tasks.health_check_exhausted_keys({})

    service.check_keys.assert_awaited_once_with(exhausted, concurrency=5, delay_seconds=1.5)


@pytest.mark.asyncio
async def test_health_check_exhausted_keys_logs_checked_and_revived(caplog):
    service = AsyncMock()
    service.list_all_keys_system_wide.return_value = [object(), object(), object()]
    service.check_keys.return_value = [
        APIKeyHealthCheckResult(key_id=1, ok=True),
        APIKeyHealthCheckResult(key_id=2, ok=False, detail="HTTP 429"),
        APIKeyHealthCheckResult(key_id=3, ok=True),
    ]

    with _patch_service(service), _patch_settings(), caplog.at_level(logging.INFO, logger=tasks.logger.name):
        await tasks.health_check_exhausted_keys({})

    assert "checked 3, revived 2" in caplog.text


@pytest.mark.asyncio
async def test_health_check_exhausted_keys_is_silent_when_no_exhausted_keys(caplog):
    service = AsyncMock()
    service.list_all_keys_system_wide.return_value = []
    service.check_keys.return_value = []

    with _patch_service(service), _patch_settings(), caplog.at_level(logging.INFO, logger=tasks.logger.name):
        await tasks.health_check_exhausted_keys({})

    assert caplog.text == ""


@pytest.mark.asyncio
async def test_purge_old_monitoring_events_uses_retention_from_settings(caplog):
    sessionmaker_patch, session = _patch_sessionmaker()
    purge = AsyncMock(return_value=7)

    with sessionmaker_patch, _patch_settings(REQUEST_EVENTS_RETENTION_DAYS=14), \
         patch.object(tasks, "purge_old_request_events", purge), \
         caplog.at_level(logging.INFO, logger=tasks.logger.name):
        await tasks.purge_old_monitoring_events({})

    purge.assert_awaited_once_with(session, older_than=timedelta(days=14))
    assert "deleted 7 row(s)" in caplog.text

