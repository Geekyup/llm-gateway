"""create request_events table

Revision ID: fbc403cce8ea
Revises: c112f7f00955
Create Date: 2026-08-02

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "fbc403cce8ea"
down_revision: Union[str, None] = "c112f7f00955"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "request_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("key_id", sa.Integer(), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("path", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("method", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("key_label", sa.String(length=255), nullable=True),
        sa.Column("upstream_status", sa.Integer(), nullable=True),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("is_retry", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("error_detail", sa.String(length=512), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_request_events_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["key_id"], ["api_keys.id"], name=op.f("fk_request_events_key_id_api_keys"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_request_events")),
    )
    op.create_index(op.f("ix_request_events_user_id"), "request_events", ["user_id"])
    op.create_index(op.f("ix_request_events_key_id"), "request_events", ["key_id"])
    op.create_index(op.f("ix_request_events_request_id"), "request_events", ["request_id"])
    op.create_index(op.f("ix_request_events_timestamp"), "request_events", ["timestamp"])
    op.create_index(
        "ix_request_events_user_key_ts", "request_events", ["user_id", "key_id", "timestamp"]
    )


def downgrade() -> None:
    op.drop_index("ix_request_events_user_key_ts", table_name="request_events")
    op.drop_index(op.f("ix_request_events_timestamp"), table_name="request_events")
    op.drop_index(op.f("ix_request_events_request_id"), table_name="request_events")
    op.drop_index(op.f("ix_request_events_key_id"), table_name="request_events")
    op.drop_index(op.f("ix_request_events_user_id"), table_name="request_events")
    op.drop_table("request_events")