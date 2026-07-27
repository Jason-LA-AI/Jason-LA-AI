"""Jason approval decision database model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.quote import Quote


class Approval(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Append-oriented request and decision record for Jason approvals."""

    __tablename__ = "approvals"
    __table_args__ = (
        CheckConstraint(
            "approval_type IN ('AVAILABILITY', 'VEHICLE_CAPACITY', 'FINAL_PRICE', "
            "'SPECIAL_ARRANGEMENT', 'LATE_NIGHT_EARLY_MORNING', "
            "'WAITING_PARKING_TOLLS_STOPS', 'CHILD_SEAT', 'SCHEDULE_CHANGE', "
            "'BOOKING_CONFIRMATION', 'CANCELLATION', 'PAYMENT_REFUND')",
            name="ck_approvals_approval_type",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'DECLINED', 'SUPERSEDED')",
            name="ck_approvals_status",
        ),
        CheckConstraint(
            "requested_by IN ('AI', 'SYSTEM', 'JASON')",
            name="ck_approvals_requested_by",
        ),
        Index("ix_approvals_status_requested_at", "status", "requested_at"),
        Index("ix_approvals_order_type", "order_id", "approval_type"),
        Index("ix_approvals_quote_type", "quote_id", "approval_type"),
    )

    order_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quote_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("quotes.id", ondelete="RESTRICT"),
    )
    # The trips table is a later implementation priority. Keep the documented
    # identifier now and add its foreign key when that model is introduced.
    trip_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    approval_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING", server_default="PENDING"
    )
    requested_by: Mapped[str] = mapped_column(String(20), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    request_summary: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    decision_by: Mapped[str | None] = mapped_column(String(100))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    decision_note: Mapped[str | None] = mapped_column(Text)

    order: Mapped["Order"] = relationship(back_populates="approvals")
    quote: Mapped["Quote | None"] = relationship(back_populates="approvals")
