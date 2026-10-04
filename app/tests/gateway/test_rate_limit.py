import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api.deps import get_gateway_token_service
from app.config import Settings, get_settings
from app.db.redis import get_redis
from app.gateway.dependencies import _enforce_rate_limit, require_gateway_token


@pytest.mark.asyncio
async def test_requests_over_limit_raise_429_with_retry_after(fake_redis):
    for _ in range(3):
        await _enforce_rate_limit(fake_redis, user_id=1, limit=3)

    with pytest.raises(HTTPException) as exc_info:
        await _enforce_rate_limit(fake_redis, user_id=1, limit=3)

    assert exc_info.value.status_code == 429
    assert 1 <= int(exc_info.value.headers["Retry-After"]) <= 60


@pytest.mark.asyncio
async def test_limit_is_tracked_per_user(fake_redis):
    for _ in range(3):
        await _enforce_rate_limit(fake_redis, user_id=1, limit=3)

    await _enforce_rate_limit(fake_redis, user_id=2, limit=3)


@pytest.mark.asyncio
async def test_zero_limit_disables_rate_limiting(fake_redis):
    for _ in range(50):
        await _enforce_rate_limit(fake_redis, user_id=1, limit=0)


class _StubTokenService:
    async def authenticate(self, plaintext: str) -> int | None:
        return 7 if plaintext == "good" else None


def _client(fake_redis, limit: int) -> TestClient:
    app = FastAPI()

    @app.get("/ping")
    async def ping(user_id: int = Depends(require_gateway_token)):
        return {"user_id": user_id}

    app.dependency_overrides[get_gateway_token_service] = lambda: _StubTokenService()
    app.dependency_overrides[get_redis] = lambda: fake_redis
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, GATEWAY_RATE_LIMIT_PER_MINUTE=limit
    )
    return TestClient(app)


def test_dependency_returns_429_once_limit_is_hit(fake_redis):
    client = _client(fake_redis, limit=2)
    headers = {"authorization": "Bearer good"}

    assert client.get("/ping", headers=headers).status_code == 200
    assert client.get("/ping", headers=headers).status_code == 200
    blocked = client.get("/ping", headers=headers)

    assert blocked.status_code == 429
    assert "retry-after" in blocked.headers


def test_invalid_token_does_not_consume_the_limit(fake_redis):
    client = _client(fake_redis, limit=1)

    assert client.get("/ping", headers={"authorization": "Bearer bad"}).status_code == 401
    assert client.get("/ping", headers={"authorization": "Bearer good"}).status_code == 200
