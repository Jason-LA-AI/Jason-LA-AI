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
    UNKNOWN_LOCATION,
    normalize_location,
    suggest_location,
)
from app.services.route_pricing import (
    CITY_MILEAGE_ARCHIVE_PRICING_SOURCE,
    RouteMileageUnavailable,
    get_archived_round_trip_mileage,
    price_range_for_miles,
)


LOS_ANGELES_TIMEZONE = ZoneInfo("America/Los_Angeles")
ROUTE_MILEAGE_PRICING_SOURCE = CITY_MILEAGE_ARCHIVE_PRICING_SOURCE
ROUTE_MILEAGE_UNAVAILABLE_PRICING_SOURCE = "route_mileage_unavailable"
# Pricing V1's long-distance band is calibrated for the established regional
# operating area.  Archive mileage beyond this closed-loop distance remains
# useful internally, but it must not produce a customer-facing auto-quote.
MAX_AUTO_QUOTE_CLOSED_LOOP_MILES = Decimal("300")
LONG_DISTANCE_REVIEW_REQUIRED = "LONG_DISTANCE_REVIEW_REQUIRED"


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

    # A customer fare needs a known canonical destination.  We do not treat a
    # free-text place or an address as normalized merely because it resembles
    # one; a future live geocoder integration must provide that confirmation.
    location_is_reliably_routable = location["normalized_city"] is not None
    if not location_is_reliably_routable:
        risk_flags.append(UNKNOWN_LOCATION)

    try:
        if not location_is_reliably_routable:
            raise RouteMileageUnavailable("Destination cannot be safely normalized.")
        # Numeric website estimates deliberately use only the audited city /
        # landmark archive. Dynamic exact-address routing remains disabled
        # until its Google Routes + geocoding validation is approved.
        road_mileage = get_archived_round_trip_mileage(
            request.service_type,
            request.airport_code,
            location_name,
        )
        mileage_price = price_range_for_miles(road_mileage.total_miles)
        minimum_amount = mileage_price.minimum_amount
        maximum_amount = mileage_price.maximum_amount
        suggested_amount = mileage_price.suggested_amount
        pricing_source = road_mileage.pricing_source
        mileage_factors = {
            "total_road_miles": str(road_mileage.total_miles.quantize(Decimal("0.1"))),
            "distance_meters": str(road_mileage.distance_meters),
            "base_route": "Rowland Heights → trip stops → Rowland Heights",
            "reference_destination": road_mileage.reference_destination,
            "location_source": "verified_city_or_landmark_archive",
            "mileage_source": "verified_closed_loop_road_mileage_archive",
            "raw_midpoint": str(mileage_price.raw_midpoint.quantize(Decimal("0.01"))),
            "rounded_midpoint": str(mileage_price.rounded_midpoint),
            "customer_range": (
                f"${mileage_price.minimum_amount}-${mileage_price.maximum_amount}"
            ),
            "range_half_width": str(mileage_price.half_width.quantize(Decimal("0.01"))),
            "pricing_rule_version": "pricing_engine_v1_model_a",
            "leg_1_road_miles": str(road_mileage.leg_1_miles.quantize(Decimal("0.1"))) if road_mileage.leg_1_miles is not None else None,
            "leg_2_road_miles": str(road_mileage.leg_2_miles.quantize(Decimal("0.1"))) if road_mileage.leg_2_miles is not None else None,
            "leg_3_road_miles": str(road_mileage.leg_3_miles.quantize(Decimal("0.1"))) if road_mileage.leg_3_miles is not None else None,
        }
        if not auto_quote_closed_loop_mileage_is_eligible(road_mileage.total_miles):
            # Retain the formula output only as an internal diagnostic.  It is
            # outside Pricing V1's validation domain and is never a suggested
            # or recommended fare.
            mileage_factors.update(
                {
                    "raw_model_midpoint": str(mileage_price.rounded_midpoint),
                    "raw_model_min": str(mileage_price.minimum_amount),
                    "raw_model_max": str(mileage_price.maximum_amount),
                    "not_for_quoting": True,
                }
            )
            mileage_factors.pop("customer_range", None)
            minimum_amount = None
            maximum_amount = None
            suggested_amount = None
            risk_flags.append(LONG_DISTANCE_REVIEW_REQUIRED)
    except RouteMileageUnavailable as exc:
        if "ROUTE_MILEAGE_UNAVAILABLE" not in risk_flags:
            risk_flags.append("ROUTE_MILEAGE_UNAVAILABLE")
        minimum_amount = None
        maximum_amount = None
        suggested_amount = None
        pricing_source = ROUTE_MILEAGE_UNAVAILABLE_PRICING_SOURCE
        mileage_factors = {
            "fallback_reason": str(exc),
            "fallback_scope": "numeric fare withheld; verified city/landmark closed-loop mileage required",
            "location_source": "unverified_or_unavailable_location",
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
                "Estimate is based on the selected city or landmark area.",
                "This is a preliminary estimate based on the route and trip details provided. Jason will review the exact pickup/drop-off location, time, luggage, and availability before confirming the final fare.",
            ]
            if pricing_source == CITY_MILEAGE_ARCHIVE_PRICING_SOURCE
            else []
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
        pricing_rule_version="pricing_engine_v1_model_a",
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
        location_suggestion=(
            suggest_location(request.location_input)
            if not customer_price_available
            else None
        ),
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

    return (
        pricing_source == CITY_MILEAGE_ARCHIVE_PRICING_SOURCE
        and not (risk_flags or [])
    )


def auto_quote_closed_loop_mileage_is_eligible(total_miles: Decimal) -> bool:
    """Return whether verified mileage is within Pricing V1's auto-quote domain."""

    return total_miles <= MAX_AUTO_QUOTE_CLOSED_LOOP_MILES


def _customer_fare_review_notice() -> str:
    return "Jason will review the exact route and confirm the fare."


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
