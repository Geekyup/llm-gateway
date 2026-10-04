"""add key_hash to api_keys

Revision ID: e4b8a1c7d9f2
Revises: a7c3e91d4b20
Create Date: 2026-10-04
"""
import hashlib
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.core.security import decrypt_key

revision: str = "e4b8a1c7d9f2"
down_revision: Union[str, None] = "a7c3e91d4b20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("api_keys", sa.Column("key_hash", sa.String(length=64), nullable=True))

    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT id, user_id, provider, key_encrypted FROM api_keys ORDER BY id")
    ).fetchall()
    seen: set[tuple[int, str, str]] = set()
    for row_id, user_id, provider, key_encrypted in rows:
        digest = hashlib.sha256(decrypt_key(key_encrypted).encode()).hexdigest()
        identity = (user_id, provider, digest)
        if identity in seen:
            continue
        seen.add(identity)
        connection.execute(
            sa.text("UPDATE api_keys SET key_hash = :key_hash WHERE id = :id"),
            {"key_hash": digest, "id": row_id},
        )

    op.create_index(
        "uq_api_keys_user_provider_hash",
        "api_keys",
        ["user_id", "provider", "key_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_api_keys_user_provider_hash", table_name="api_keys")
    op.drop_column("api_keys", "key_hash")
