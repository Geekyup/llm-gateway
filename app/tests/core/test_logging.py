import json
import logging

import pytest

from app.core.logging import JsonFormatter, configure_logging
from app.core.request_context import request_id_var


@pytest.fixture
def restore_logging():
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    access = logging.getLogger("uvicorn.access")
    disabled = access.disabled
    yield
    root.handlers[:] = handlers
    root.setLevel(level)
    access.disabled = disabled


def _record(message: str = "hello", **extra) -> logging.LogRecord:
    record = logging.LogRecord("app.test", logging.INFO, __file__, 1, message, (), None)
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_json_formatter_emits_core_fields_and_extras():
    record = _record("served %s", request_id="abc", status=200, duration_ms=12.5)
    record.args = ("ok",)

    payload = json.loads(JsonFormatter().format(record))

    assert payload["message"] == "served ok"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.test"
    assert payload["request_id"] == "abc"
    assert payload["status"] == 200
    assert payload["duration_ms"] == 12.5
    assert payload["timestamp"].endswith("+00:00")


def test_json_formatter_reads_request_id_from_context_when_filter_is_absent():
    token = request_id_var.set("from-context")
    try:
        payload = json.loads(JsonFormatter().format(_record()))
    finally:
        request_id_var.reset(token)

    assert payload["request_id"] == "from-context"


def test_json_formatter_uses_null_without_request_id():
    payload = json.loads(JsonFormatter().format(_record(request_id="-")))

    assert payload["request_id"] is None


def test_json_formatter_includes_exception_text():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = logging.LogRecord("app.test", logging.ERROR, __file__, 1, "failed", (), sys.exc_info())

    payload = json.loads(JsonFormatter().format(record))

    assert "ValueError: boom" in payload["exception"]


def test_json_formatter_does_not_let_extras_override_core_fields():
    payload = json.loads(JsonFormatter().format(_record("real", level="FAKE", logger="fake")))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.test"


def test_configured_json_logs_carry_the_current_request_id(capsys, restore_logging):
    configure_logging(fmt="json")
    token = request_id_var.set("req-123")
    try:
        logging.getLogger("app.demo").info("something happened")
    finally:
        request_id_var.reset(token)

    line = capsys.readouterr().out.strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["message"] == "something happened"
    assert payload["request_id"] == "req-123"


def test_configured_text_logs_show_request_id_or_dash(capsys, restore_logging):
    configure_logging(fmt="text")
    logger = logging.getLogger("app.demo")

    logger.info("outside request")
    token = request_id_var.set("req-456")
    try:
        logger.info("inside request")
    finally:
        request_id_var.reset(token)

    lines = capsys.readouterr().out.strip().splitlines()
    assert "[-] outside request" in lines[-2]
    assert "[req-456] inside request" in lines[-1]


def test_configure_logging_silences_uvicorn_access_and_routes_uvicorn_through_root(restore_logging):
    configure_logging(fmt="json")

    assert logging.getLogger("uvicorn.access").disabled is True
    assert logging.getLogger("uvicorn.error").propagate is True
    assert logging.getLogger("uvicorn.error").handlers == []


def test_debug_flag_sets_debug_level(restore_logging):
    configure_logging(debug=True)

    assert logging.getLogger().level == logging.DEBUG
