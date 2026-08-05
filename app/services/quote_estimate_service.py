"""Development-only structured quote estimate generation."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.quote_estimate import QuoteEstimate
from app.schemas.quote_estimate import (
    LargeLuggageCount,
    PassengerCount,
    QuoteEstimateCreate,
    QuoteEstimateResponse,
    QuoteEstimateStatus,
    QuoteServiceType,
    QuoteVehicleAssessment,
)
from app.services.location_normalizer import UNKNOWN_LOCATION, normalize_location


LOS_ANGELES_TIMEZONE = ZoneInfo("America/Los_Angeles")
DEVELOPMENT_PRICING_SOURCE = "development_mock"
LONG_DISTANCE_LOCATIONS = {"san diego", "san jose", "santa barbara", "las vegas"}

DEVELOPMENT_MOCK_RANGES: dict[str, tuple[Decimal, Decimal]] = {
    "LAX": (Decimal("130.00"), Decimal("150.00")),
    "ONT": (Decimal("100.00"), Decimal("140.00")),
    "SNA": (Decimal("120.00"), Decimal("160.00")),
    "BUR": (Decimal("120.00"), Decimal("150.00")),
    "LGB": (Decimal("120.00"), Decimal("150.00")),
}


def create_quote_estimate(
    request: QuoteEstimateCreate,
    db_session: Session,
) -> QuoteEstimateResponse:
    """Calculate, persist, and return a structured development estimate."""

    now = datetime.now(LOS_ANGELES_TIMEZONE)
    if request.service_date < now.date():
        raise ValueError("service_date cannot be earlier than today in Los Angeles")

    location = normalize_location(request.location_input)
    location_name = location["normalized_city"] or location["input"]
    route_summary = _build_route_summary(request, location_name)
    risk_flags = _risk_flags(request)

    unknown_location = location["pricing_zone"] == UNKNOWN_LOCATION
    if unknown_location:
        risk_flags.append(UNKNOWN_LOCATION)
    long_distance_route = _is_long_distance_location(location["input"])
    if long_distance_route:
        risk_flags.append("LONG_DISTANCE_ROUTE")

    manual_review_required = bool(risk_flags)
    minimum_amount, maximum_amount = DEVELOPMENT_MOCK_RANGES[request.airport_code.value]
    suggested_amount = (minimum_amount + maximum_amount) / Decimal("2")
    if long_distance_route:
        minimum_amount = None
        maximum_amount = None
        suggested_amount = None
    if manual_review_required:
        status = QuoteEstimateStatus.MANUAL_REVIEW_REQUIRED
        vehicle_assessment = _manual_vehicle_assessment(request, unknown_location)
        notices = [
            "Manual review required.",
            "Jason will confirm vehicle availability and final price.",
            f"Pricing source: {DEVELOPMENT_PRICING_SOURCE}.",
            "Development mock only. This is not a real quote.",
        ]
    else:
        status = QuoteEstimateStatus.ESTIMATED
        vehicle_assessment = QuoteVehicleAssessment.LIKELY_COMFORTABLE
        notices = [
            "This is an estimated range.",
            "Final price requires Jason confirmation.",
            f"Pricing source: {DEVELOPMENT_PRICING_SOURCE}.",
            "Development mock only. This is not a real quote.",
        ]

    passenger_count, passenger_count_is_minimum = _passenger_count_values(request)
    large_suitcase_count, large_suitcase_count_is_minimum = _luggage_count_values(request)
    expires_at = now + timedelta(hours=24)
    estimate = QuoteEstimate(
        status=status.value,
        service_type=request.service_type.value,
        airport_code=request.airport_code.value,
        service_date=request.service_date,
        service_time=request.service_time,
        service_timezone=request.service_timezone,
        service_datetime=datetime.combine(
            request.service_date,
            request.service_time.replace(tzinfo=None),
            tzinfo=LOS_ANGELES_TIMEZONE,
        ),
        flight_number=request.flight_number,
        location_input=location["input"],
        location_input_type=location["input_type"],
        normalized_city=location["normalized_city"],
        postal_code=location["postal_code"],
        pricing_zone=location["pricing_zone"],
        route_summary=route_summary,
        passenger_count=passenger_count,
        passenger_count_is_minimum=passenger_count_is_minimum,
        large_suitcase_count=large_suitcase_count,
        large_suitcase_count_is_minimum=large_suitcase_count_is_minimum,
        child_seat_required="YES" if request.child_seat_required else "NO",
        oversized_items_present=request.oversized_items,
        estimated_min_amount=minimum_amount,
        estimated_max_amount=maximum_amount,
        suggested_amount=suggested_amount,
        currency_code="USD",
        pricing_source=DEVELOPMENT_PRICING_SOURCE,
        pricing_rule_version="development_mock_v1",
        pricing_factors={
            "airport_code": request.airport_code.value,
            "pricing_zone": location["pricing_zone"],
            "service_type": request.service_type.value,
        },
        vehicle_assessment=vehicle_assessment.value,
        risk_flags=risk_flags,
        manual_review_reason=", ".join(risk_flags) if risk_flags else None,
        requires_jason_review=True,
        expires_at=expires_at,
    )

    try:
        db_session.add(estimate)
        db_session.flush()
        db_session.refresh(estimate)
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise

    return QuoteEstimateResponse(
        estimate_id=estimate.id,
        status=QuoteEstimateStatus(estimate.status),
        route_summary=estimate.route_summary,
        estimated_min_amount=estimate.estimated_min_amount,
        estimated_max_amount=estimate.estimated_max_amount,
        currency_code="USD",
        vehicle_assessment=QuoteVehicleAssessment(estimate.vehicle_assessment),
        requires_jason_review=estimate.requires_jason_review,
        risk_flags=estimate.risk_flags or [],
        notices=notices,
        valid_until=estimate.expires_at,
    )


def _build_route_summary(request: QuoteEstimateCreate, location_name: str) -> str:
    airport = request.airport_code.value
    if request.service_type == QuoteServiceType.AIRPORT_PICKUP:
        return f"{airport} → {location_name}"
    return f"{location_name} → {airport}"


def _risk_flags(request: QuoteEstimateCreate) -> list[str]:
    flags: list[str] = []
    if request.passenger_count == PassengerCount.FIVE_PLUS:
        flags.append("PASSENGER_COUNT_5_PLUS")
    if request.large_luggage_count == LargeLuggageCount.FOUR_PLUS:
        flags.append("LARGE_LUGGAGE_4_PLUS")
    if request.oversized_items:
        flags.append("OVERSIZED_ITEMS")
    return flags


def _is_long_distance_location(location_input: str) -> bool:
    """Return whether the customer location requires custom long-distance pricing."""

    normalized = " ".join(location_input.casefold().replace(",", " ").split())
    suffixes = (" ca", " california", " nv", " nevada")
    for suffix in suffixes:
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
            break
    return normalized in LONG_DISTANCE_LOCATIONS


def _passenger_count_values(request: QuoteEstimateCreate) -> tuple[int, bool]:
    if request.passenger_count == PassengerCount.FIVE_PLUS:
        return 5, True
    return int(request.passenger_count.value), False


def _luggage_count_values(request: QuoteEstimateCreate) -> tuple[int, bool]:
    if request.large_luggage_count == LargeLuggageCount.FOUR_PLUS:
        return 4, True
    return int(request.large_luggage_count.value), False


def _manual_vehicle_assessment(
    request: QuoteEstimateCreate,
    unknown_location: bool,
) -> QuoteVehicleAssessment:
    if request.passenger_count == PassengerCount.FIVE_PLUS:
        return QuoteVehicleAssessment.NOT_RECOMMENDED
    if unknown_location:
        return QuoteVehicleAssessment.INSUFFICIENT_INFORMATION
    return QuoteVehicleAssessment.NEEDS_CONFIRMATION
