"""create api_keys table

Revision ID: 978f546ad8dd
Revises:
Create Date: 2026-07-20

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "978f546ad8dd"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("key_encrypted", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("requests_today", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("daily_limit", sa.Integer(), nullable=False),
        sa.Column("cooldown_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_keys")),
    )
    op.create_index(op.f("ix_api_keys_provider"), "api_keys", ["provider"], unique=False)
    op.create_index(op.f("ix_api_keys_status"), "api_keys", ["status"], unique=False)
    op.create_index("ix_api_keys_provider_status", "api_keys", ["provider", "status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_api_keys_provider_status", table_name="api_keys")
    op.drop_index(op.f("ix_api_keys_status"), table_name="api_keys")
    op.drop_index(op.f("ix_api_keys_provider"), table_name="api_keys")
    op.drop_table("api_keys")
