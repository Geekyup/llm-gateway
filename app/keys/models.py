from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.keys.enums import KeyStatus, ProviderType


class APIKey(TimestampMixin, Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[ProviderType] = mapped_column(
        Enum(ProviderType, name="provider_type", native_enum=False, length=32),
        nullable=False,
        index=True,
    )
    key_encrypted: Mapped[str] = mapped_column(String(512), nullable=False)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[KeyStatus] = mapped_column(
        Enum(KeyStatus, name="key_status", native_enum=False, length=32),
        nullable=False,
        default=KeyStatus.ACTIVE,
        server_default=KeyStatus.ACTIVE.value,
        index=True,
    )
    requests_today: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    daily_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_api_keys_user_provider_status", "user_id", "provider", "status"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug convenience only
        return f"<APIKey id={self.id} label={self.label!r} provider={self.provider} status={self.status}>"
