"""Notification delivery intent database model."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Notification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A channel-neutral notification awaiting delivery."""

    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "channel IN ('TELEGRAM', 'SMS', 'EMAIL')",
            name="ck_notifications_channel",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'SENT', 'FAILED')",
            name="ck_notifications_status",
        ),
        CheckConstraint(
            "attempt_count >= 0",
            name="ck_notifications_attempt_count",
        ),
        Index("ix_notifications_status_created_at", "status", "created_at"),
        Index("ix_notifications_approval_id", "approval_id"),
        Index("ix_notifications_order_id", "order_id"),
    )

    channel: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="PENDING", server_default="PENDING"
    )
    template_key: Mapped[str] = mapped_column(String(100), nullable=False)
    recipient: Mapped[str | None] = mapped_column(String(255))
    approval_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    order_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    quote_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    provider: Mapped[str | None] = mapped_column(String(50))
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    last_error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
