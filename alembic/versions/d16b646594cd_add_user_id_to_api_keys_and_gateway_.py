"""add user_id to api_keys and gateway_tokens

Revision ID: d16b646594cd
Revises: dc35daee9dbd
Create Date: 2026-07-23

Ties both the upstream provider key pool (api_keys) and the
client-facing gateway tokens (gateway_tokens) to a single owning user,
so one account can never see or use another account's keys, tokens,
or request history.

Existing rows (from before per-user isolation existed) have no owner
to infer, so this migration deletes them rather than guessing — any
pre-existing keys/tokens must be re-created by their real owner after
upgrading. If that's not acceptable for a given deployment, back up
api_keys/gateway_tokens before running this migration and re-assign
user_id manually instead of deleting.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d16b646594cd"
down_revision: Union[str, None] = "dc35daee9dbd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No owner can be inferred for rows created under the old shared-pool
    # model — remove them rather than leaving user_id nullable/ambiguous.
    op.execute("DELETE FROM api_keys")
    op.execute("DELETE FROM gateway_tokens")

    op.add_column("api_keys", sa.Column("user_id", sa.Integer(), nullable=False))
    op.create_index(op.f("ix_api_keys_user_id"), "api_keys", ["user_id"])
    op.create_foreign_key(
        op.f("fk_api_keys_user_id_users"),
        "api_keys",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    # Hot path query becomes "active keys for this user+provider" — extend
    # the existing (provider, status) index rather than adding a third.
    op.drop_index(op.f("ix_api_keys_provider_status"), table_name="api_keys")
    op.create_index(
        "ix_api_keys_user_provider_status", "api_keys", ["user_id", "provider", "status"]
    )

    op.add_column("gateway_tokens", sa.Column("user_id", sa.Integer(), nullable=False))
    op.create_index(op.f("ix_gateway_tokens_user_id"), "gateway_tokens", ["user_id"])
    op.create_foreign_key(
        op.f("fk_gateway_tokens_user_id_users"),
        "gateway_tokens",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("fk_gateway_tokens_user_id_users"), "gateway_tokens", type_="foreignkey")
    op.drop_index(op.f("ix_gateway_tokens_user_id"), table_name="gateway_tokens")
    op.drop_column("gateway_tokens", "user_id")

    op.drop_index("ix_api_keys_user_provider_status", table_name="api_keys")
    op.create_index("ix_api_keys_provider_status", "api_keys", ["provider", "status"])
    op.drop_constraint(op.f("fk_api_keys_user_id_users"), "api_keys", type_="foreignkey")
    op.drop_index(op.f("ix_api_keys_user_id"), table_name="api_keys")
    op.drop_column("api_keys", "user_id")
