from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RequestEventRecord(Base):
    __tablename__ = "request_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key_id: Mapped[int | None] = mapped_column(
        ForeignKey("api_keys.id", ondelete="SET NULL"), nullable=True, index=True
    )
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    path: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="")
    method: Mapped[str] = mapped_column(String(16), nullable=False, default="", server_default="")
    key_label: Mapped[str | None] = mapped_column(String(255), nullable=True)

    upstream_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_retry: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
    error_detail: Mapped[str | None] = mapped_column(String(512), nullable=True)

    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_request_events_user_key_ts", "user_id", "key_id", "timestamp"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug convenience only
        return f"<RequestEventRecord id={self.id} user_id={self.user_id} key_id={self.key_id} outcome={self.outcome!r}>"