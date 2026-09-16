"""Compatibility pricing entry point using the closed-loop road-mileage rule."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.services.location_normalizer import normalize_location
from app.services.route_pricing import (
    AIRPORT_ADDRESSES,
    RouteMileageUnavailable,
    get_archived_round_trip_mileage,
    price_range_for_miles,
)


@dataclass
class PricingResult:
    """Internal pricing recommendation; all amounts require Jason approval."""

    suggested_amount: Decimal | None
    minimum_amount: Decimal | None
    maximum_amount: Decimal | None
    pricing_source: str
    factors: dict[str, str]
    requires_jason_approval: bool = True


def calculate_price(
    airport: str | None,
    destination: str | None,
    pickup_time: str | None = None,
    service_type: str | None = None,
) -> PricingResult:
    """Return a fare only for an available closed-loop road route.

    This legacy entry point is used by chat and inquiry flows. It deliberately
    has no route-price table and no numeric fallback: unavailable mileage is an
    internal review result.
    """

    del pickup_time
    if not airport or airport not in AIRPORT_ADDRESSES or not destination:
        return _review_result("airport or destination is missing or unsupported")
    if service_type not in {"AIRPORT_PICKUP", "AIRPORT_DROPOFF"}:
        # Older chat/inquiry callers do not always know whether the customer
        # is going to or coming from an airport. A pickup-loop quote would be
        # unsafe for a dropoff, so withhold a number until the direction is
        # explicit.
        return _review_result("service direction is missing or unsupported")

    location = normalize_location(destination)
    if location["normalized_city"] is None:
        return _review_result("UNKNOWN_LOCATION")

    customer_location = location["normalized_city"] or location["input"]
    try:
        # This legacy customer-facing helper also stays on the verified archive
        # path. It must not surface a dynamic exact-address or old fallback
        # amount while Pricing Engine V1 is in effect.
        mileage = get_archived_round_trip_mileage(
            service_type, airport, customer_location
        )
        price = price_range_for_miles(mileage.total_miles)
    except RouteMileageUnavailable as exc:
        return _review_result(str(exc))

    factors = {
        "total_road_miles": str(mileage.total_miles.quantize(Decimal("0.1"))),
        "leg_1_road_miles": _formatted_miles(mileage.leg_1_miles),
        "leg_2_road_miles": _formatted_miles(mileage.leg_2_miles),
        "leg_3_road_miles": _formatted_miles(mileage.leg_3_miles),
        "raw_midpoint": str(price.raw_midpoint.quantize(Decimal("0.01"))),
        "rounded_midpoint": str(price.rounded_midpoint),
        "customer_range": f"${price.minimum_amount}-${price.maximum_amount}",
        "pricing_rule_version": "pricing_engine_v1_model_a",
        "location_source": "verified_city_or_landmark_archive",
        "mileage_source": "verified_closed_loop_road_mileage_archive",
    }
    return PricingResult(
        suggested_amount=price.suggested_amount,
        minimum_amount=price.minimum_amount,
        maximum_amount=price.maximum_amount,
        pricing_source=mileage.pricing_source,
        factors=factors,
    )


def _review_result(reason: str) -> PricingResult:
    return PricingResult(
        suggested_amount=None,
        minimum_amount=None,
        maximum_amount=None,
        pricing_source="route_mileage_unavailable",
        factors={"manual_review_reason": reason},
    )


def _formatted_miles(value: Decimal | None) -> str:
    return str(value.quantize(Decimal("0.1"))) if value is not None else "unavailable"
