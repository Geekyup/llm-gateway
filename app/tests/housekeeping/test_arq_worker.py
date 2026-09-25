import importlib

from app.housekeeping import arq_worker


def _cron_by_name(worker_settings) -> dict:
    return {job.name: job for job in worker_settings.cron_jobs}


def test_reset_daily_limits_uses_minute_from_settings(monkeypatch):
    monkeypatch.setenv("HOUSEKEEPING_RESET_CRON_MINUTE", "15")
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        reloaded = importlib.reload(arq_worker)
        job = _cron_by_name(reloaded.WorkerSettings)["cron:reset_daily_limits"]
        assert job.minute == 15
        assert job.hour == 0
    finally:
        get_settings.cache_clear()
        monkeypatch.delenv("HOUSEKEEPING_RESET_CRON_MINUTE")
        importlib.reload(arq_worker)


def test_all_four_housekeeping_jobs_are_registered():
    names = set(_cron_by_name(arq_worker.WorkerSettings))

    assert names == {
        "cron:clear_expired_cooldowns",
        "cron:reset_daily_limits",
        "cron:health_check_exhausted_keys",
        "cron:purge_old_monitoring_events",
    }


def test_health_check_job_has_explicit_timeout_from_settings():
    job = _cron_by_name(arq_worker.WorkerSettings)["cron:health_check_exhausted_keys"]

    assert job.timeout_s == 1500

