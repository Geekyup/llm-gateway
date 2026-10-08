import json
import logging

import httpx
import pytest
from fastapi import FastAPI
from prometheus_client import REGISTRY

from app.core.logging import configure_logging
from app.core.middleware import REQUEST_ID_HEADER, RequestContextMiddleware
from app.core.request_context import get_request_id


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/whoami")
    async def whoami():
        logging.getLogger("app.handler").info("inside handler")
        return {"request_id": get_request_id()}

    @app.get("/items/{item_id}")
    async def item(item_id: str):
        return {"id": item_id}

    @app.get("/boom")
    async def boom():
        raise RuntimeError("secret internal detail")

    return app


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=_build_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


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


def _sample(name: str, **labels) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


async def test_generates_a_request_id_and_exposes_it_to_handlers_and_clients(client):
    response = await client.get("/whoami")

    header = response.headers[REQUEST_ID_HEADER]
    assert len(header) == 32
    assert response.json() == {"request_id": header}


async def test_reuses_a_valid_incoming_request_id(client):
    response = await client.get("/whoami", headers={REQUEST_ID_HEADER: "trace-abc.123_x"})

    assert response.headers[REQUEST_ID_HEADER] == "trace-abc.123_x"
    assert response.json() == {"request_id": "trace-abc.123_x"}


@pytest.mark.parametrize("incoming", ["has spaces", "x" * 65, "semi;colon", "<script>"])
async def test_replaces_an_invalid_incoming_request_id(client, incoming):
    response = await client.get("/whoami", headers={REQUEST_ID_HEADER: incoming})

    assert response.headers[REQUEST_ID_HEADER] != incoming
    assert len(response.headers[REQUEST_ID_HEADER]) == 32


async def test_each_request_gets_its_own_id(client):
    first = await client.get("/whoami")
    second = await client.get("/whoami")

    assert first.headers[REQUEST_ID_HEADER] != second.headers[REQUEST_ID_HEADER]


async def test_request_id_does_not_leak_outside_the_request(client):
    await client.get("/whoami")

    assert get_request_id() is None


async def test_unhandled_error_returns_500_with_request_id_and_hides_details(client):
    response = await client.get("/boom")

    body = response.json()
    assert response.status_code == 500
    assert body["detail"] == "Internal server error"
    assert body["request_id"] == response.headers[REQUEST_ID_HEADER]
    assert "secret internal detail" not in response.text


async def test_metrics_use_route_templates_not_raw_paths(client):
    before = _sample("http_requests_total", method="GET", route="/items/{item_id}", status="200")

    await client.get("/items/1")
    await client.get("/items/2")

    after = _sample("http_requests_total", method="GET", route="/items/{item_id}", status="200")
    assert after - before == 2
    assert _sample("http_requests_total", method="GET", route="/items/1", status="200") == 0


async def test_unknown_paths_are_counted_under_one_label(client):
    before = _sample("http_requests_total", method="GET", route="unmatched", status="404")

    await client.get("/does-not-exist-1")
    await client.get("/does-not-exist-2")

    after = _sample("http_requests_total", method="GET", route="unmatched", status="404")
    assert after - before == 2


async def test_unhandled_errors_are_counted_as_500(client):
    before = _sample("http_requests_total", method="GET", route="/boom", status="500")

    await client.get("/boom")

    assert _sample("http_requests_total", method="GET", route="/boom", status="500") - before == 1


async def test_duration_histogram_records_each_request(client):
    before = _sample("http_request_duration_seconds_count", method="GET", route="/whoami")

    await client.get("/whoami")

    assert _sample("http_request_duration_seconds_count", method="GET", route="/whoami") - before == 1


async def test_in_progress_gauge_returns_to_its_previous_value(client):
    before = _sample("http_requests_in_progress")

    await client.get("/whoami")
    await client.get("/boom")

    assert _sample("http_requests_in_progress") == before


async def test_access_log_line_is_structured_and_matches_the_response_header(client, capsys, restore_logging):
    configure_logging(fmt="json")

    response = await client.get("/items/7")

    lines = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]
    access = next(line for line in lines if line["logger"] == "app.access")
    assert access["request_id"] == response.headers[REQUEST_ID_HEADER]
    assert access["method"] == "GET"
    assert access["path"] == "/items/7"
    assert access["route"] == "/items/{item_id}"
    assert access["status"] == 200
    assert access["duration_ms"] >= 0


async def test_application_logs_inside_a_handler_carry_the_same_request_id(client, capsys, restore_logging):
    configure_logging(fmt="json")

    response = await client.get("/whoami")

    lines = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]
    handler_line = next(line for line in lines if line["message"] == "inside handler")
    assert handler_line["request_id"] == response.headers[REQUEST_ID_HEADER]


async def test_unhandled_error_is_logged_with_traceback_and_request_id(client, capsys, restore_logging):
    configure_logging(fmt="json")

    response = await client.get("/boom")

    lines = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]
    error_line = next(line for line in lines if line["message"] == "unhandled error")
    assert error_line["request_id"] == response.headers[REQUEST_ID_HEADER]
    assert "RuntimeError: secret internal detail" in error_line["exception"]


async def test_health_style_paths_are_logged_at_debug_only(capsys, restore_logging):
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    configure_logging(fmt="json")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
        await http_client.get("/health")

    assert "app.access" not in capsys.readouterr().out
