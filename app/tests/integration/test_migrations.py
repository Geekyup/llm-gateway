import os
import subprocess
import sys
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.auth.models import RefreshToken, User  # noqa: F401
from app.core.security import encrypt_key
from app.db.base import Base
from app.keys.models import APIKey  # noqa: F401
from app.monitoring.models import RequestEventRecord  # noqa: F401
from app.tokens.models import GatewayToken  # noqa: F401

pytestmark = pytest.mark.integration

_ROOT = Path(__file__).resolve().parents[3]
_REVISION_BEFORE_KEY_HASH = "a7c3e91d4b20"


def _alembic(*args: str) -> None:
    env = {**os.environ, "DATABASE_URL": os.environ["TEST_DATABASE_URL"]}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.fixture
async def clean_engine():
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"], poolclass=NullPool)

    async def reset() -> None:
        async with engine.begin() as conn:
            await conn.execute(text("DROP SCHEMA public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))

    await reset()
    yield engine
    await reset()
    await engine.dispose()


async def test_migrations_produce_the_schema_the_models_describe(clean_engine):
    _alembic("upgrade", "head")

    def diff(sync_conn):
        return compare_metadata(MigrationContext.configure(sync_conn), Base.metadata)

    async with clean_engine.connect() as conn:
        differences = await conn.run_sync(diff)

    assert differences == []


async def test_every_migration_can_be_downgraded_and_reapplied(clean_engine):
    _alembic("upgrade", "head")
    _alembic("downgrade", "base")
    _alembic("upgrade", "head")


async def test_key_hash_migration_backfills_hashes_and_keeps_duplicates(clean_engine):
    _alembic("upgrade", _REVISION_BEFORE_KEY_HASH)
    duplicate = encrypt_key("same-raw-key")
    async with clean_engine.begin() as conn:
        await conn.execute(text("INSERT INTO users (id, google_sub, email) VALUES (1, 'sub', 'a@b.c')"))
        for label, encrypted in (
            ("first", duplicate),
            ("copy", encrypt_key("same-raw-key")),
            ("other", encrypt_key("different-raw-key")),
        ):
            await conn.execute(
                text(
                    "INSERT INTO api_keys (user_id, label, provider, key_encrypted, daily_limit) "
                    "VALUES (1, :label, 'GEMINI', :encrypted, 100)"
                ),
                {"label": label, "encrypted": encrypted},
            )

    _alembic("upgrade", "head")

    async with clean_engine.connect() as conn:
        rows = (
            await conn.execute(text("SELECT label, key_hash FROM api_keys ORDER BY id"))
        ).all()
    hashes = dict(rows)
    assert hashes["first"] is not None
    assert hashes["other"] is not None
    assert hashes["first"] != hashes["other"]
    assert hashes["copy"] is None
