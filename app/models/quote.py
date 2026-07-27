"""Quote database model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.approval import Approval
    from app.models.order import Order


class Quote(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Versioned internal suggestion and customer-facing quote."""

    __tablename__ = "quotes"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT', 'WAITING_FOR_JASON_APPROVAL', 'APPROVED', "
            "'SENT', 'ACCEPTED', 'DECLINED', 'SUPERSEDED')",
            name="ck_quotes_status",
        ),
        CheckConstraint(
            "quote_type IN ('ONE_WAY', 'ROUND_TRIP', 'OTHER')",
            name="ck_quotes_quote_type",
        ),
        CheckConstraint("version_number >= 1", name="ck_quotes_version_number"),
        CheckConstraint(
            "suggested_min_amount IS NULL OR suggested_min_amount >= 0",
            name="ck_quotes_suggested_min_amount",
        ),
        CheckConstraint(
            "suggested_max_amount IS NULL OR suggested_max_amount >= 0",
            name="ck_quotes_suggested_max_amount",
        ),
        CheckConstraint(
            "suggested_amount IS NULL OR suggested_amount >= 0",
            name="ck_quotes_suggested_amount",
        ),
        CheckConstraint(
            "final_quoted_amount IS NULL OR final_quoted_amount >= 0",
            name="ck_quotes_final_quoted_amount",
        ),
        UniqueConstraint("order_id", "version_number", name="uq_quotes_order_version"),
        Index("ix_quotes_order_status", "order_id", "status"),
    )

    order_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="DRAFT", server_default="DRAFT"
    )
    currency_code: Mapped[str] = mapped_column(
        String(3), nullable=False, default="USD", server_default="USD"
    )
    suggested_min_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    suggested_max_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    suggested_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    final_quoted_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    quote_type: Mapped[str] = mapped_column(String(20), nullable=False)
    exact_route_match: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    pricing_source: Mapped[str | None] = mapped_column(Text)
    pricing_limitations: Mapped[str | None] = mapped_column(Text)
    additional_fee_factors: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    approved_inclusions: Mapped[str | None] = mapped_column(Text)
    approved_exclusions: Mapped[str | None] = mapped_column(Text)
    internal_notes: Mapped[str | None] = mapped_column(Text)
    knowledge_version: Mapped[str | None] = mapped_column(String(100))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    customer_responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    order: Mapped["Order"] = relationship(back_populates="quotes")
    approvals: Mapped[list["Approval"]] = relationship(back_populates="quote")
