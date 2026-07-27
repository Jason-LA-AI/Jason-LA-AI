"""Conversation message database model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.lead import Lead
    from app.models.order import Order


class Conversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One incoming, outgoing, internal, or system message."""

    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint(
            "channel IN ('XIAOHONGSHU', 'FACEBOOK', 'GOOGLE_WEBSITE', 'TELEGRAM', "
            "'PHONE', 'EMAIL', 'MANUAL', 'OTHER')",
            name="ck_conversations_channel",
        ),
        CheckConstraint(
            "direction IN ('INBOUND', 'OUTBOUND', 'INTERNAL', 'SYSTEM')",
            name="ck_conversations_direction",
        ),
        CheckConstraint(
            "sender_type IN ('CUSTOMER', 'JASON', 'AI', 'SYSTEM')",
            name="ck_conversations_sender_type",
        ),
        CheckConstraint(
            "delivery_status IS NULL OR delivery_status IN "
            "('DRAFT', 'PENDING', 'SENT', 'DELIVERED', 'FAILED', 'NOT_APPLICABLE')",
            name="ck_conversations_delivery_status",
        ),
        CheckConstraint(
            "direction <> 'INTERNAL' OR customer_visible = false",
            name="ck_conversations_internal_not_customer_visible",
        ),
        Index("ix_conversations_customer_created_at", "customer_id", "created_at"),
        Index("ix_conversations_lead_created_at", "lead_id", "created_at"),
        Index("ix_conversations_order_created_at", "order_id", "created_at"),
        Index(
            "uq_conversations_channel_external_message",
            "channel",
            "external_message_id",
            unique=True,
            postgresql_where=text("external_message_id IS NOT NULL"),
        ),
    )

    customer_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    lead_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="SET NULL"),
    )
    order_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="SET NULL"),
    )
    channel: Mapped[str] = mapped_column(String(30), nullable=False)
    external_conversation_id: Mapped[str | None] = mapped_column(String(255))
    external_message_id: Mapped[str | None] = mapped_column(String(255))
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    sender_type: Mapped[str] = mapped_column(String(20), nullable=False)
    sender_identifier: Mapped[str | None] = mapped_column(String(255))
    language_code: Mapped[str | None] = mapped_column(String(20))
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    attachment_metadata: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(JSONB)
    customer_visible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    ai_generated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    approval_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivery_status: Mapped[str | None] = mapped_column(String(20))
    raw_event_reference: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    customer: Mapped["Customer"] = relationship(back_populates="conversations")
    lead: Mapped["Lead | None"] = relationship(back_populates="conversations")
    order: Mapped["Order | None"] = relationship(back_populates="conversations")
