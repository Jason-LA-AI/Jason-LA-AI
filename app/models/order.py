"""Order database model."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, SmallInteger, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.approval import Approval
    from app.models.conversation import Conversation
    from app.models.customer import Customer
    from app.models.lead import Lead
    from app.models.quote import Quote
    from app.models.quote_estimate import QuoteEstimate


class Order(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One operational transportation trip leg."""

    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('NEW', 'WAITING_FOR_INFORMATION', 'QUOTED', "
            "'WAITING_FOR_JASON_APPROVAL', 'CONFIRMED', 'COMPLETED', 'CANCELLED')",
            name="ck_orders_status",
        ),
        CheckConstraint(
            "intent IN ('AIRPORT_PICKUP', 'AIRPORT_DROPOFF', "
            "'PRIVATE_TRANSPORTATION', 'LONG_DISTANCE')",
            name="ck_orders_intent",
        ),
        CheckConstraint(
            "trip_direction IS NULL OR trip_direction = 'ONE_WAY'",
            name="ck_orders_trip_direction",
        ),
        CheckConstraint(
            "flight_scope IS NULL OR flight_scope IN "
            "('DOMESTIC', 'INTERNATIONAL', 'NOT_APPLICABLE', 'UNKNOWN')",
            name="ck_orders_flight_scope",
        ),
        CheckConstraint(
            "child_seat_required IN ('YES', 'NO', 'UNKNOWN')",
            name="ck_orders_child_seat_required",
        ),
        CheckConstraint(
            "vehicle_assessment IN ('LIKELY_COMFORTABLE', 'NEEDS_CONFIRMATION', "
            "'NOT_RECOMMENDED', 'INSUFFICIENT_INFORMATION')",
            name="ck_orders_vehicle_assessment",
        ),
        CheckConstraint(
            "risk_level IS NULL OR risk_level IN ('LOW', 'MEDIUM', 'HIGH')",
            name="ck_orders_risk_level",
        ),
        CheckConstraint(
            "priority_score IS NULL OR priority_score BETWEEN 0 AND 100",
            name="ck_orders_priority_score",
        ),
        CheckConstraint(
            "priority_level IS NULL OR priority_level IN ('P1', 'P2', 'P3', 'P4', 'P5')",
            name="ck_orders_priority_level",
        ),
        CheckConstraint(
            "next_action_owner IS NULL OR next_action_owner IN ('AI', 'JASON', 'CUSTOMER')",
            name="ck_orders_next_action_owner",
        ),
        CheckConstraint(
            "cancelled_by IS NULL OR cancelled_by IN ('CUSTOMER', 'JASON', 'UNKNOWN')",
            name="ck_orders_cancelled_by",
        ),
        CheckConstraint(
            "passenger_count IS NULL OR passenger_count >= 0",
            name="ck_orders_passenger_count",
        ),
        CheckConstraint("adult_count IS NULL OR adult_count >= 0", name="ck_orders_adult_count"),
        CheckConstraint("child_count IS NULL OR child_count >= 0", name="ck_orders_child_count"),
        CheckConstraint(
            "large_suitcase_count IS NULL OR large_suitcase_count >= 0",
            name="ck_orders_large_suitcase_count",
        ),
        CheckConstraint(
            "carry_on_count IS NULL OR carry_on_count >= 0",
            name="ck_orders_carry_on_count",
        ),
        CheckConstraint(
            "NOT passenger_count_is_minimum OR "
            "(passenger_count IS NOT NULL AND passenger_count = 5)",
            name="ck_orders_passenger_count_minimum",
        ),
        CheckConstraint(
            "NOT large_suitcase_count_is_minimum OR "
            "(large_suitcase_count IS NOT NULL AND large_suitcase_count = 4)",
            name="ck_orders_large_suitcase_count_minimum",
        ),
        Index("ix_orders_status_pickup_at", "status", "pickup_at"),
        Index("ix_orders_customer_service_date", "customer_id", "service_date"),
        Index("ix_orders_airport_service_date", "airport_code", "service_date"),
        Index("ix_orders_route_cities", "pickup_city", "destination_city"),
        Index(
            "uq_orders_quote_estimate_id",
            "quote_estimate_id",
            unique=True,
            postgresql_where=text("quote_estimate_id IS NOT NULL"),
        ),
    )

    booking_group_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    customer_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    lead_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="SET NULL"),
    )
    quote_estimate_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("quote_estimates.id", ondelete="RESTRICT"),
    )
    status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="NEW", server_default="NEW"
    )
    intent: Mapped[str] = mapped_column(String(40), nullable=False)
    service_date: Mapped[date | None] = mapped_column(Date)
    pickup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    service_timezone: Mapped[str] = mapped_column(
        String(50), nullable=False, default="America/Los_Angeles", server_default="America/Los_Angeles"
    )
    trip_direction: Mapped[str | None] = mapped_column(String(20))
    airport_code: Mapped[str | None] = mapped_column(String(3))
    flight_scope: Mapped[str | None] = mapped_column(String(20))
    airline: Mapped[str | None] = mapped_column(String(100))
    flight_number: Mapped[str | None] = mapped_column(String(30))
    scheduled_flight_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    terminal: Mapped[str | None] = mapped_column(String(50))
    pickup_location: Mapped[str | None] = mapped_column(Text)
    pickup_city: Mapped[str | None] = mapped_column(String(100))
    destination: Mapped[str | None] = mapped_column(Text)
    destination_city: Mapped[str | None] = mapped_column(String(100))
    postal_code: Mapped[str | None] = mapped_column(String(10))
    pricing_zone: Mapped[str | None] = mapped_column(String(50))
    extra_stops: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    passenger_count: Mapped[int | None] = mapped_column(SmallInteger)
    passenger_count_is_minimum: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    adult_count: Mapped[int | None] = mapped_column(SmallInteger)
    child_count: Mapped[int | None] = mapped_column(SmallInteger)
    large_suitcase_count: Mapped[int | None] = mapped_column(SmallInteger)
    large_suitcase_count_is_minimum: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    large_suitcase_details: Mapped[str | None] = mapped_column(Text)
    carry_on_count: Mapped[int | None] = mapped_column(SmallInteger)
    oversized_items_present: Mapped[bool | None] = mapped_column(Boolean)
    oversized_item_details: Mapped[str | None] = mapped_column(Text)
    child_seat_required: Mapped[str] = mapped_column(
        String(10), nullable=False, default="UNKNOWN", server_default="UNKNOWN"
    )
    child_seat_details: Mapped[str | None] = mapped_column(Text)
    special_requests: Mapped[str | None] = mapped_column(Text)
    pickup_coordination_notes: Mapped[str | None] = mapped_column(Text)
    vehicle_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="2026 Toyota RAV4 Hybrid LE",
        server_default="2026 Toyota RAV4 Hybrid LE",
    )
    vehicle_assessment: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="INSUFFICIENT_INFORMATION",
        server_default="INSUFFICIENT_INFORMATION",
    )
    vehicle_assessment_reason: Mapped[str | None] = mapped_column(Text)
    risk_level: Mapped[str | None] = mapped_column(String(10))
    risk_reason: Mapped[str | None] = mapped_column(Text)
    priority_score: Mapped[int | None] = mapped_column(SmallInteger)
    priority_level: Mapped[str | None] = mapped_column(String(10))
    missing_information: Mapped[list[str] | None] = mapped_column(JSONB)
    next_action: Mapped[str | None] = mapped_column(Text)
    next_action_owner: Mapped[str | None] = mapped_column(String(20))
    follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    customer_details_reconfirmed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    customer_estimate_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    confirmation_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by: Mapped[str | None] = mapped_column(String(20))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
    internal_notes: Mapped[str | None] = mapped_column(Text)
    knowledge_version: Mapped[str | None] = mapped_column(String(100))

    customer: Mapped["Customer"] = relationship(back_populates="orders")
    lead: Mapped["Lead | None"] = relationship(back_populates="orders")
    quote_estimate: Mapped["QuoteEstimate | None"] = relationship()
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="order")
    quotes: Mapped[list["Quote"]] = relationship(back_populates="order")
    approvals: Mapped[list["Approval"]] = relationship(back_populates="order")
