from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from llm_gateway.db.base import Base, TimestampMixin
from llm_gateway.keys.enums import KeyStatus, ProviderType


class APIKey(TimestampMixin, Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Owning account. Every query against this table must filter by this —
    # there is no "global pool" anymore, each user has their own.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Human-friendly label so an admin can tell keys apart without decrypting
    # them, e.g. "gemini-personal-acct-2". Never contains the secret itself.
    label: Mapped[str] = mapped_column(String(255), nullable=False)

    provider: Mapped[ProviderType] = mapped_column(
        Enum(ProviderType, name="provider_type", native_enum=False, length=32),
        nullable=False,
        index=True,
    )

    # Fernet ciphertext, base64-encoded text — never store or log the plaintext.
    key_encrypted: Mapped[str] = mapped_column(String(512), nullable=False)

    status: Mapped[KeyStatus] = mapped_column(
        Enum(KeyStatus, name="key_status", native_enum=False, length=32),
        nullable=False,
        default=KeyStatus.ACTIVE,
        server_default=KeyStatus.ACTIVE.value,
        index=True,
    )

    requests_today: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    daily_limit: Mapped[int] = mapped_column(Integer, nullable=False)

    # Set when a 429 puts the key into COOLDOWN; housekeeping clears status
    # once this timestamp is in the past (or immediately on next-day reset).
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        # The hot query on the request path: "give me this user's active keys
        # for provider X". user_id leads so it can also serve plain
        # "list my keys" lookups without a separate index.
        Index("ix_api_keys_user_provider_status", "user_id", "provider", "status"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug convenience only
        return f"<APIKey id={self.id} label={self.label!r} provider={self.provider} status={self.status}>"
