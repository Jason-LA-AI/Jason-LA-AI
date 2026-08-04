"""Pydantic contracts for structured V2.1 quote estimates."""

from datetime import date, datetime, time
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator


LOS_ANGELES_TIMEZONE = ZoneInfo("America/Los_Angeles")


class QuoteServiceType(StrEnum):
    """Airport transportation directions supported by V2.1."""

    AIRPORT_PICKUP = "AIRPORT_PICKUP"
    AIRPORT_DROPOFF = "AIRPORT_DROPOFF"


class QuoteAirportCode(StrEnum):
    """Airports supported by the structured estimate flow."""

    LAX = "LAX"
    ONT = "ONT"
    SNA = "SNA"
    BUR = "BUR"
    LGB = "LGB"


class PassengerCount(StrEnum):
    """Passenger-count choices exposed by the quote form."""

    ONE = "1"
    TWO = "2"
    THREE = "3"
    FOUR = "4"
    FIVE_PLUS = "5+"


class LargeLuggageCount(StrEnum):
    """Large-luggage choices exposed by the quote form."""

    ZERO = "0"
    ONE = "1"
    TWO = "2"
    THREE = "3"
    FOUR_PLUS = "4+"


class QuoteEstimateStatus(StrEnum):
    """Customer-safe estimate lifecycle states."""

    ESTIMATED = "ESTIMATED"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
    ACCEPTED = "ACCEPTED"
    CONVERTED = "CONVERTED"
    EXPIRED = "EXPIRED"
    INVALIDATED = "INVALIDATED"


class QuoteVehicleAssessment(StrEnum):
    """Vehicle assessment vocabulary shared with the current models."""

    LIKELY_COMFORTABLE = "LIKELY_COMFORTABLE"
    NEEDS_CONFIRMATION = "NEEDS_CONFIRMATION"
    NOT_RECOMMENDED = "NOT_RECOMMENDED"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"


class QuoteEstimateCreate(BaseModel):
    """Validated structured trip details used to request an estimate."""

    model_config = ConfigDict(str_strip_whitespace=True)

    service_type: QuoteServiceType
    airport_code: QuoteAirportCode
    service_date: date
    service_time: time
    service_timezone: Literal["America/Los_Angeles"] = "America/Los_Angeles"
    location_input: str = Field(min_length=1, max_length=80)
    passenger_count: PassengerCount
    large_luggage_count: LargeLuggageCount
    child_seat_required: bool
    oversized_items: bool

    @field_validator("service_date")
    @classmethod
    def service_date_must_not_be_in_past(cls, value: date) -> date:
        """Reject dates earlier than today in Los Angeles."""

        today_in_los_angeles = datetime.now(LOS_ANGELES_TIMEZONE).date()
        if value < today_in_los_angeles:
            raise ValueError("service_date cannot be earlier than today in Los Angeles")
        return value


class QuoteEstimateResponse(BaseModel):
    """Public estimate result returned to the structured quote page."""

    estimate_id: UUID
    status: QuoteEstimateStatus
    route_summary: str
    estimated_min_amount: Decimal | None
    estimated_max_amount: Decimal | None
    currency_code: Literal["USD"] = "USD"
    vehicle_assessment: QuoteVehicleAssessment
    requires_jason_review: bool
    risk_flags: list[str] = Field(default_factory=list)
    notices: list[str] = Field(default_factory=list)
    valid_until: datetime
