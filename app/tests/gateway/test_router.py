import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_gateway_service
from app.gateway.dependencies import require_gateway_token
from app.gateway.router import router
from app.keys.enums import ProviderType


class RecordingGateway:
    def __init__(self) -> None:
        self.specs: list = []

    async def proxy_request(self, *, user_id, build_request, provider_type=None, model=None):
        self.specs.append(build_request(None))
        return httpx.Response(200, json={"ok": True}), provider_type or ProviderType.GEMINI


@pytest.fixture
def gateway() -> RecordingGateway:
    return RecordingGateway()


@pytest.fixture
def client(gateway: RecordingGateway) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_gateway_service] = lambda: gateway
    app.dependency_overrides[require_gateway_token] = lambda: 1
    return TestClient(app)


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/v1/gemini/v1beta/models/gemini-2.0-flash:generateContent"),
        ("POST", "/v1/gemini/v1beta/models/gemini-2.0-flash:streamGenerateContent"),
        ("GET", "/v1/gemini/v1beta/models"),
        ("GET", "/v1/gemini/v1beta/models/gemini-2.0-flash"),
        ("POST", "/v1/groq/v1/chat/completions"),
        ("POST", "/v1/openrouter/v1/embeddings"),
        ("GET", "/v1/openrouter/v1/models"),
        ("GET", "/v1/openrouter/v1/models/openai/gpt-4o-mini"),
    ],
)
def test_allowed_paths_are_proxied(client, gateway, method, path):
    response = client.request(method, path, json={"a": 1} if method == "POST" else None)

    assert response.status_code == 200
    assert len(gateway.specs) == 1


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/v1/openrouter/v1/key"),
        ("GET", "/v1/openrouter/v1/auth/key"),
        ("POST", "/v1/groq/v1/models"),
        ("GET", "/v1/groq/v1/chat/completions"),
        ("GET", "/v1/gemini/v1beta/tunedModels"),
        ("POST", "/v1/gemini/v1beta/models/x:deleteEverything"),
        ("GET", "/v1/gemini/v1beta/models/../../v1beta/files"),
        ("GET", "/v1/groq/v1/models/%2e%2e/%2e%2e/admin"),
        ("POST", "/v1/groq/v1//chat/completions"),
    ],
)
def test_other_paths_are_rejected_without_hitting_gateway(client, gateway, method, path):
    response = client.request(method, path, json={} if method == "POST" else None)

    assert response.status_code == 404
    assert gateway.specs == []


def test_unknown_provider_is_404(client):
    response = client.post("/v1/nope/v1/chat/completions", json={})

    assert response.status_code == 404
    assert response.json()["error"] == "unknown_provider"


def test_invalid_json_body_is_400_not_500(client, gateway):
    response = client.post(
        "/v1/groq/v1/chat/completions",
        content=b"{not json",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_json"
    assert gateway.specs == []


def test_non_object_json_body_is_400(client):
    response = client.post("/v1/groq/v1/chat/completions", json=[1, 2, 3])

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_json"


def test_only_allowlisted_headers_are_forwarded(client, gateway):
    client.post(
        "/v1/groq/v1/chat/completions",
        json={"a": 1},
        headers={
            "accept": "application/json",
            "cookie": "session=secret",
            "x-forwarded-for": "1.2.3.4",
            "x-goog-api-key": "stolen",
            "user-agent": "curl",
        },
    )

    assert gateway.specs[0].headers == {"accept": "application/json"}
