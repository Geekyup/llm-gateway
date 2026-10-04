from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.core.body_limit import BodySizeLimitMiddleware


def _client(max_bytes: int) -> TestClient:
    app = FastAPI()
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=max_bytes)

    @app.post("/echo")
    async def echo(request: Request):
        body = await request.body()
        return {"size": len(body)}

    return TestClient(app)


def test_body_within_limit_passes():
    response = _client(100).post("/echo", content=b"x" * 100)

    assert response.status_code == 200
    assert response.json() == {"size": 100}


def test_declared_content_length_over_limit_is_413():
    response = _client(100).post("/echo", content=b"x" * 101)

    assert response.status_code == 413


def test_chunked_body_over_limit_is_413():
    def chunks():
        for _ in range(5):
            yield b"x" * 30

    response = _client(100).post("/echo", content=chunks())

    assert response.status_code == 413
