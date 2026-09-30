"""add last_ping_ms and last_ping_at to api_keys

Revision ID: a7c3e91d4b20
Revises: 10a2f5cb3bce
Create Date: 2026-09-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7c3e91d4b20"
down_revision: Union[str, None] = "10a2f5cb3bce"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("api_keys", sa.Column("last_ping_ms", sa.Integer(), nullable=True))
    op.add_column("api_keys", sa.Column("last_ping_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("api_keys", "last_ping_at")
    op.drop_column("api_keys", "last_ping_ms")
