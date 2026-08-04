"""Transactional outbox event database model."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class OutboxEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An event committed atomically for later asynchronous delivery."""

    __tablename__ = "outbox_events"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'PROCESSED', 'FAILED')",
            name="ck_outbox_events_status",
        ),
        CheckConstraint(
            "attempt_count >= 0",
            name="ck_outbox_events_attempt_count",
        ),
        Index("ix_outbox_events_status_available_at", "status", "available_at"),
        Index(
            "ix_outbox_events_aggregate",
            "aggregate_type",
            "aggregate_id",
        ),
    )

    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(50), nullable=False)
    aggregate_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING", server_default="PENDING"
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=func.now(), server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
