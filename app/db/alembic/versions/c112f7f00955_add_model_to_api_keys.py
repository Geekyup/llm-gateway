"""add model to api_keys

Revision ID: c112f7f00955
Revises: d16b646594cd
Create Date: 2026-07-26

Lets a key be pinned to a specific upstream model (e.g.
"gemini-3.6-flash" or "openai/gpt-4o-mini") so a client's chat/completions
request only draws from keys configured for the model it asked for.
Nullable and unindexed for now — filtering happens in Python over the
already-narrow "active keys for this user+provider" result set, so a DB
index isn't worth the write overhead at this scale. Existing keys get
NULL, which the selector treats as "never matches a model-specific
request" (see KeyPoolService.get_candidate_keys).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c112f7f00955"
down_revision: Union[str, None] = "d16b646594cd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("api_keys", sa.Column("model", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("api_keys", "model")
