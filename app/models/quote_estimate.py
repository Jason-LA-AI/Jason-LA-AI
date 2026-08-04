"""Anonymous structured quote estimate database model."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    Time,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class QuoteEstimate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Temporary structured estimate before a customer creates an inquiry."""

    __tablename__ = "quote_estimates"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ESTIMATED', 'MANUAL_REVIEW_REQUIRED', 'ACCEPTED', "
            "'CONVERTED', 'EXPIRED', 'INVALIDATED')",
            name="ck_quote_estimates_status",
        ),
        CheckConstraint(
            "service_type IN ('AIRPORT_PICKUP', 'AIRPORT_DROPOFF')",
            name="ck_quote_estimates_service_type",
        ),
        CheckConstraint(
            "airport_code IN ('LAX', 'ONT', 'SNA', 'BUR', 'LGB')",
            name="ck_quote_estimates_airport_code",
        ),
        CheckConstraint(
            "location_input_type IN ('ZIP', 'CITY')",
            name="ck_quote_estimates_location_input_type",
        ),
        CheckConstraint(
            "passenger_count BETWEEN 1 AND 5",
            name="ck_quote_estimates_passenger_count",
        ),
        CheckConstraint(
            "NOT passenger_count_is_minimum OR passenger_count = 5",
            name="ck_quote_estimates_passenger_count_minimum",
        ),
        CheckConstraint(
            "large_suitcase_count BETWEEN 0 AND 4",
            name="ck_quote_estimates_large_suitcase_count",
        ),
        CheckConstraint(
            "NOT large_suitcase_count_is_minimum OR large_suitcase_count = 4",
            name="ck_quote_estimates_large_suitcase_count_minimum",
        ),
        CheckConstraint(
            "child_seat_required IN ('YES', 'NO', 'UNKNOWN')",
            name="ck_quote_estimates_child_seat_required",
        ),
        CheckConstraint(
            "estimated_min_amount IS NULL OR estimated_min_amount >= 0",
            name="ck_quote_estimates_min_amount",
        ),
        CheckConstraint(
            "estimated_max_amount IS NULL OR estimated_max_amount >= 0",
            name="ck_quote_estimates_max_amount",
        ),
        CheckConstraint(
            "suggested_amount IS NULL OR suggested_amount >= 0",
            name="ck_quote_estimates_suggested_amount",
        ),
        CheckConstraint(
            "estimated_min_amount IS NULL OR estimated_max_amount IS NULL "
            "OR estimated_min_amount <= estimated_max_amount",
            name="ck_quote_estimates_amount_range",
        ),
        CheckConstraint(
            "status <> 'ESTIMATED' OR "
            "(estimated_min_amount IS NOT NULL AND estimated_max_amount IS NOT NULL)",
            name="ck_quote_estimates_estimated_amounts_present",
        ),
        CheckConstraint(
            "currency_code = 'USD'",
            name="ck_quote_estimates_currency_code",
        ),
        CheckConstraint(
            "vehicle_assessment IN ('LIKELY_COMFORTABLE', 'NEEDS_CONFIRMATION', "
            "'NOT_RECOMMENDED', 'INSUFFICIENT_INFORMATION')",
            name="ck_quote_estimates_vehicle_assessment",
        ),
        Index("ix_quote_estimates_status_expires_at", "status", "expires_at"),
        Index("ix_quote_estimates_airport_pricing_zone", "airport_code", "pricing_zone"),
        Index("ix_quote_estimates_service_datetime", "service_datetime"),
    )

    status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="ESTIMATED", server_default="ESTIMATED"
    )
    service_type: Mapped[str] = mapped_column(String(40), nullable=False)
    airport_code: Mapped[str] = mapped_column(String(3), nullable=False)
    service_date: Mapped[date] = mapped_column(Date, nullable=False)
    service_time: Mapped[time] = mapped_column(Time(timezone=False), nullable=False)
    service_timezone: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="America/Los_Angeles",
        server_default="America/Los_Angeles",
    )
    service_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    location_input: Mapped[str] = mapped_column(String(255), nullable=False)
    location_input_type: Mapped[str] = mapped_column(String(20), nullable=False)
    normalized_city: Mapped[str | None] = mapped_column(String(100))
    postal_code: Mapped[str | None] = mapped_column(String(10))
    pricing_zone: Mapped[str | None] = mapped_column(String(50))
    route_summary: Mapped[str] = mapped_column(String(255), nullable=False)

    passenger_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    passenger_count_is_minimum: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    large_suitcase_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    large_suitcase_count_is_minimum: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    child_seat_required: Mapped[str] = mapped_column(String(10), nullable=False)
    oversized_items_present: Mapped[bool] = mapped_column(Boolean, nullable=False)

    estimated_min_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    estimated_max_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    suggested_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    currency_code: Mapped[str] = mapped_column(
        String(3), nullable=False, default="USD", server_default="USD"
    )

    pricing_source: Mapped[str | None] = mapped_column(String(100))
    pricing_rule_version: Mapped[str] = mapped_column(String(100), nullable=False)
    pricing_factors: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    vehicle_assessment: Mapped[str] = mapped_column(String(30), nullable=False)
    risk_flags: Mapped[list[str] | None] = mapped_column(JSONB)
    manual_review_reason: Mapped[str | None] = mapped_column(Text)
    requires_jason_review: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
