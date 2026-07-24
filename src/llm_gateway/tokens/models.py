from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from llm_gateway.db.base import Base, TimestampMixin


class GatewayToken(TimestampMixin, Base):
    """A client-facing token that unifies access to one user's key pool.

    This is deliberately separate from APIKey (the upstream provider keys)
    and from ADMIN_API_KEY (which guards /admin/* management endpoints).
    A GatewayToken is what an external application uses to call
    POST /v1/{provider}/... — it never sees which upstream key served the
    request, only that the call succeeded. Every GatewayToken belongs to
    exactly one user, and a request authenticated with it can only ever
    draw from that same user's api_keys.

    Only a salted hash of the token is stored; the plaintext is generated
    once, shown to the admin exactly one time, and never persisted or
    logged anywhere.
    """

    __tablename__ = "gateway_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Owning account — determines whose api_keys this token can draw from.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Human-friendly label, e.g. "kitroom-backend", "mobile-app-prod".
    label: Mapped[str] = mapped_column(String(255), nullable=False)

    # sha256 hex digest of the plaintext token — never store the plaintext.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    # First/last few characters of the plaintext, kept only for the admin
    # to visually recognize a token in a list without revealing the secret.
    token_preview: Mapped[str] = mapped_column(String(32), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debug convenience only
        return f"<GatewayToken id={self.id} label={self.label!r} active={self.is_active}>"
