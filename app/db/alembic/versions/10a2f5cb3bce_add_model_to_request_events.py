"""add model column and user/ts index to request_events

Revision ID: 10a2f5cb3bce
Revises: fbc403cce8ea
Create Date: 2026-08-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "10a2f5cb3bce"
down_revision: Union[str, None] = "fbc403cce8ea"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("request_events", sa.Column("model", sa.String(length=128), nullable=True))
    op.create_index(op.f("ix_request_events_model"), "request_events", ["model"])
    op.create_index("ix_request_events_user_ts", "request_events", ["user_id", "timestamp"])


def downgrade() -> None:
    op.drop_index("ix_request_events_user_ts", table_name="request_events")
    op.drop_index(op.f("ix_request_events_model"), table_name="request_events")
    op.drop_column("request_events", "model")
