from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest

from app.providers.base import parse_retry_after


def _response(value: str | None) -> httpx.Response:
    headers = {} if value is None else {"retry-after": value}
    return httpx.Response(429, headers=headers)


def test_missing_header_gives_none():
    assert parse_retry_after(_response(None)) is None


@pytest.mark.parametrize(("raw", "expected"), [("7", 7), ("0", 0), ("120", 120), (" 30 ", 30)])
def test_integer_seconds(raw, expected):
    assert parse_retry_after(_response(raw)) == expected


@pytest.mark.parametrize(("raw", "expected"), [("2.5", 3), ("0.2", 1), ("1.0", 1)])
def test_fractional_seconds_round_up(raw, expected):
    assert parse_retry_after(_response(raw)) == expected


def test_http_date_in_the_future_is_converted_to_seconds():
    moment = datetime.now(UTC) + timedelta(seconds=90)

    seconds = parse_retry_after(_response(format_datetime(moment, usegmt=True)))

    assert seconds is not None
    assert 88 <= seconds <= 91


def test_http_date_in_the_past_means_retry_now():
    moment = datetime.now(UTC) - timedelta(minutes=5)

    assert parse_retry_after(_response(format_datetime(moment, usegmt=True))) == 0


@pytest.mark.parametrize("raw", ["soon", "", "-5", "nan", "inf", "12abc"])
def test_garbage_and_negative_values_are_ignored(raw):
    assert parse_retry_after(_response(raw)) is None
