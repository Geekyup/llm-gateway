import os
from urllib.parse import urlparse

import pytest
import pytest_asyncio
from redis.asyncio import Redis

_REASON = "needs real PostgreSQL and Redis: set TEST_DATABASE_URL (postgresql+asyncpg://...) and TEST_REDIS_URL"


def _services_configured() -> bool:
    database_url = os.environ.get("TEST_DATABASE_URL", "")
    return database_url.startswith("postgresql") and bool(os.environ.get("TEST_REDIS_URL"))


def pytest_collection_modifyitems(items):
    if _services_configured():
        return
    skip = pytest.mark.skip(reason=_REASON)
    for item in items:
        if item.get_closest_marker("integration"):
            item.add_marker(skip)


@pytest_asyncio.fixture
async def redis_client():
    database = urlparse(os.environ["TEST_REDIS_URL"]).path.lstrip("/")
    if database in ("", "0"):
        raise RuntimeError(
            "TEST_REDIS_URL must select a dedicated logical database (for example redis://localhost:6379/1): "
            "the fixture runs FLUSHDB"
        )
    client = Redis.from_url(os.environ["TEST_REDIS_URL"], decode_responses=True)
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()
