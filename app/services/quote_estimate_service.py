"""Structured airport quote estimates based on round-trip road mileage."""

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
from app.services.location_normalizer import (
    normalize_location,
)
from app.services.route_pricing import (
    CITY_MILEAGE_ARCHIVE_PRICING_SOURCE,
    GOOGLE_ROUTES_PRICING_SOURCE,
    RouteMileageUnavailable,
    get_round_trip_mileage,
    price_range_for_route,
)


LOS_ANGELES_TIMEZONE = ZoneInfo("America/Los_Angeles")
ROUTE_MILEAGE_PRICING_SOURCE = GOOGLE_ROUTES_PRICING_SOURCE
TEMPORARY_REFERENCE_PRICING_SOURCE = "temporary_airport_reference_v1"

# Emergency customer-facing fallback until the road-mileage archive or Maps
# API is available. These are planning ranges, not final fares.
TEMPORARY_AIRPORT_RANGES: dict[str, tuple[Decimal, Decimal]] = {
    "LAX": (Decimal("130"), Decimal("150")),
    "ONT": (Decimal("100"), Decimal("140")),
    "SNA": (Decimal("120"), Decimal("160")),
    "BUR": (Decimal("120"), Decimal("150")),
    "LGB": (Decimal("120"), Decimal("150")),
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

    try:
        road_mileage = get_round_trip_mileage(
            request.service_type,
            request.airport_code,
            location_name,
        )
        mileage_price = price_range_for_route(
            road_mileage.total_miles,
            request.airport_code.value,
            road_mileage.reference_destination,
        )
        minimum_amount = mileage_price.minimum_amount
        maximum_amount = mileage_price.maximum_amount
        suggested_amount = mileage_price.suggested_amount
        pricing_source = road_mileage.pricing_source
        mileage_factors = {
            "total_road_miles": str(road_mileage.total_miles.quantize(Decimal("0.1"))),
            "distance_meters": str(road_mileage.distance_meters),
            "base_route": "Rowland Heights → trip stops → Rowland Heights",
            "reference_destination": road_mileage.reference_destination,
        }
    except RouteMileageUnavailable:
        risk_flags.append("ROUTE_MILEAGE_UNAVAILABLE")
        minimum_amount, maximum_amount = TEMPORARY_AIRPORT_RANGES[
            request.airport_code.value
        ]
        suggested_amount = (minimum_amount + maximum_amount) / Decimal("2")
        pricing_source = TEMPORARY_REFERENCE_PRICING_SOURCE
        mileage_factors = {
            "fallback_reason": "road mileage unavailable",
            "fallback_scope": "airport reference only; replace with closed-loop mileage",
        }

    manual_review_required = bool(risk_flags)
    if manual_review_required:
        status = QuoteEstimateStatus.MANUAL_REVIEW_REQUIRED
        vehicle_assessment = _manual_vehicle_assessment(request)
        notices = [
            "Jason will review your trip details and confirm the fare.",
        ]
    else:
        status = QuoteEstimateStatus.ESTIMATED
        vehicle_assessment = QuoteVehicleAssessment.LIKELY_COMFORTABLE
        notices = (
            [
                "This range is based on a precomputed city-center road route.",
                "Final price requires Jason confirmation.",
            ]
            if pricing_source == CITY_MILEAGE_ARCHIVE_PRICING_SOURCE
            else [
                "This is an estimated range.",
                "Final price requires Jason confirmation.",
            ]
        )

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
        pricing_source=pricing_source,
        pricing_rule_version="round_trip_mileage_v1",
        pricing_factors={
            "airport_code": request.airport_code.value,
            "pricing_zone": location["pricing_zone"],
            "service_type": request.service_type.value,
            **mileage_factors,
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

    customer_price_available = customer_numeric_fare_is_available(
        pricing_source=estimate.pricing_source,
        risk_flags=estimate.risk_flags,
    )
    customer_notices = (
        notices
        if customer_price_available
        else [_customer_fare_review_notice()]
    )
    return QuoteEstimateResponse(
        estimate_id=estimate.id,
        status=QuoteEstimateStatus(estimate.status),
        route_summary=estimate.route_summary,
        estimated_min_amount=(estimate.estimated_min_amount if customer_price_available else None),
        estimated_max_amount=(estimate.estimated_max_amount if customer_price_available else None),
        currency_code="USD",
        vehicle_assessment=QuoteVehicleAssessment(estimate.vehicle_assessment),
        requires_jason_review=estimate.requires_jason_review,
        risk_flags=estimate.risk_flags or [],
        notices=customer_notices,
        valid_until=estimate.expires_at,
    )


def customer_numeric_fare_is_available(
    *,
    pricing_source: str | None,
    risk_flags: list[str] | None,
) -> bool:
    """Apply the single customer-facing fare-display policy.

    Only an actual road-mileage calculation can show a customer fare.
    """

    if pricing_source == TEMPORARY_REFERENCE_PRICING_SOURCE:
        return True
    return (
        pricing_source in {
            ROUTE_MILEAGE_PRICING_SOURCE,
            CITY_MILEAGE_ARCHIVE_PRICING_SOURCE,
        }
        and "ROUTE_MILEAGE_UNAVAILABLE" not in (risk_flags or [])
    )


def _customer_fare_review_notice() -> str:
    return "Road mileage is temporarily unavailable. Jason will confirm the fare."


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
) -> QuoteVehicleAssessment:
    if request.passenger_count == PassengerCount.FIVE_PLUS:
        return QuoteVehicleAssessment.NOT_RECOMMENDED
    return QuoteVehicleAssessment.NEEDS_CONFIRMATION
