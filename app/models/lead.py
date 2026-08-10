"""Lead database model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, SmallInteger, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.customer import Customer
    from app.models.order import Order


class Lead(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Customer inquiry before and during qualification."""

    __tablename__ = "leads"
    __table_args__ = (
        CheckConstraint(
            "source IN ('WEBSITE', 'XIAOHONGSHU', 'FACEBOOK', 'GOOGLE', "
            "'REFERRAL', 'OTHER', 'UNKNOWN')",
            name="ck_leads_source",
        ),
        CheckConstraint(
            "intent IS NULL OR intent IN ('AIRPORT_PICKUP', 'AIRPORT_DROPOFF', "
            "'PRIVATE_TRANSPORTATION', 'LONG_DISTANCE')",
            name="ck_leads_intent",
        ),
        CheckConstraint(
            "status IN ('NEW', 'AWAITING_DETAILS', 'PENDING_JASON', 'QUOTED', "
            "'FOLLOW_UP', 'CONVERTED', 'LOST', 'UNAVAILABLE')",
            name="ck_leads_status",
        ),
        CheckConstraint(
            "next_action_owner IS NULL OR next_action_owner IN ('AI', 'JASON', 'CUSTOMER')",
            name="ck_leads_next_action_owner",
        ),
        CheckConstraint(
            "vehicle_assessment IS NULL OR vehicle_assessment IN "
            "('LIKELY_COMFORTABLE', 'NEEDS_CONFIRMATION', 'NOT_RECOMMENDED', "
            "'INSUFFICIENT_INFORMATION')",
            name="ck_leads_vehicle_assessment",
        ),
        CheckConstraint(
            "risk_level IS NULL OR risk_level IN ('LOW', 'MEDIUM', 'HIGH')",
            name="ck_leads_risk_level",
        ),
        CheckConstraint(
            "priority_score IS NULL OR priority_score BETWEEN 0 AND 100",
            name="ck_leads_priority_score",
        ),
        CheckConstraint(
            "priority_level IS NULL OR priority_level IN ('P1', 'P2', 'P3', 'P4', 'P5')",
            name="ck_leads_priority_level",
        ),
        CheckConstraint(
            "priority_override IS NULL OR priority_override IN "
            "('AVOID_RECOMMENDED', 'INFORMATION_REQUIRED', 'JASON_REVIEW_REQUIRED')",
            name="ck_leads_priority_override",
        ),
        CheckConstraint(
            "intake_method IN "
            "('FREE_TEXT', 'STRUCTURED_QUOTE_V2', 'MANUAL', 'DEVELOPMENT_SEED')",
            name="ck_leads_intake_method",
        ),
        Index("ix_leads_status_follow_up_at", "status", "follow_up_at"),
        Index("ix_leads_priority_received_at", "priority_level", "received_at"),
        Index("ix_leads_customer_received_at", "customer_id", "received_at"),
        Index(
            "uq_leads_idempotency_key",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    customer_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    external_conversation_id: Mapped[str | None] = mapped_column(String(255))
    intent: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="NEW", server_default="NEW"
    )
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_contact_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_action: Mapped[str | None] = mapped_column(Text)
    next_action_owner: Mapped[str | None] = mapped_column(String(20))
    follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    missing_information: Mapped[list[str] | None] = mapped_column(JSONB)
    analysis_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    customer_message_summary: Mapped[str | None] = mapped_column(Text)
    route_summary: Mapped[str | None] = mapped_column(Text)
    intake_method: Mapped[str] = mapped_column(
        String(40), nullable=False, default="FREE_TEXT", server_default="FREE_TEXT"
    )
    estimate_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str | None] = mapped_column(String(100))
    vehicle_assessment: Mapped[str | None] = mapped_column(String(30))
    risk_level: Mapped[str | None] = mapped_column(String(10))
    risk_reason: Mapped[str | None] = mapped_column(Text)
    priority_score: Mapped[int | None] = mapped_column(SmallInteger)
    priority_level: Mapped[str | None] = mapped_column(String(10))
    priority_override: Mapped[str | None] = mapped_column(String(30))
    jason_decision_needed: Mapped[str | None] = mapped_column(Text)
    lost_reason: Mapped[str | None] = mapped_column(Text)
    knowledge_version: Mapped[str | None] = mapped_column(String(100))

    customer: Mapped["Customer"] = relationship(back_populates="leads")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="lead")
    orders: Mapped[list["Order"]] = relationship(back_populates="lead")
