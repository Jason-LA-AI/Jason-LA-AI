"""Road-mileage lookup and mileage-based quote rules."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import TYPE_CHECKING

import requests

from app.config.settings import settings
from app.services.city_mileage_archive import lookup_archived_mileage

if TYPE_CHECKING:
    from app.schemas.quote_estimate import QuoteAirportCode, QuoteServiceType


GOOGLE_ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
METERS_PER_MILE = Decimal("1609.344")
MODEL_A_BASE_FARE = Decimal("33.53")
MODEL_A_FIRST_BAND_MILES = Decimal("50")
MODEL_A_SECOND_BAND_END_MILES = Decimal("130")
MODEL_A_FIRST_BAND_RATE = Decimal("1.00")
MODEL_A_SECOND_BAND_RATE = Decimal("0.90")
MODEL_A_LONG_BAND_RATE = Decimal("0.40")
CITY_MILEAGE_ARCHIVE_PRICING_SOURCE = "city_mileage_pricing_v1"
GOOGLE_ROUTES_PRICING_SOURCE = "google_routes_mileage_v1"

AIRPORT_ADDRESSES = {
    "LAX": "Los Angeles International Airport, 1 World Way, Los Angeles, CA 90045",
    "ONT": "Ontario International Airport, Ontario, CA 91761",
    "SNA": "John Wayne Airport, Santa Ana, CA 92707",
    "BUR": "Hollywood Burbank Airport, Burbank, CA 91505",
    "LGB": "Long Beach Airport, Long Beach, CA 90808",
}


class RouteMileageUnavailable(RuntimeError):
    """Raised when a safe road-mileage result cannot be obtained."""


@dataclass(frozen=True)
class RouteMileage:
    """A closed-loop road distance returned by the routes provider."""

    total_miles: Decimal
    distance_meters: int
    pricing_source: str = GOOGLE_ROUTES_PRICING_SOURCE
    reference_destination: str | None = None
    leg_1_miles: Decimal | None = None
    leg_2_miles: Decimal | None = None
    leg_3_miles: Decimal | None = None


@dataclass(frozen=True)
class MileagePriceRange:
    """The public planning range derived solely from total road miles."""

    minimum_amount: Decimal
    maximum_amount: Decimal
    suggested_amount: Decimal
    raw_midpoint: Decimal
    rounded_midpoint: Decimal
    half_width: Decimal


def get_archived_round_trip_mileage(
    service_type: "QuoteServiceType",
    airport_code: "QuoteAirportCode",
    customer_location: str,
) -> RouteMileage:
    """Return only a verified city/landmark archive closed-loop route.

    This is the customer-estimate safe path. It never calls a dynamic routing
    provider, because exact-address routing has not yet been production
    validated for Jason's estimate flow.
    """

    service_type_value = getattr(service_type, "value", service_type)
    airport_code_value = getattr(airport_code, "value", airport_code)
    archived_mileage = lookup_archived_mileage(
        service_type=service_type_value,
        airport_code=airport_code_value,
        location=customer_location,
    )
    if archived_mileage is None:
        raise RouteMileageUnavailable(
            "Verified city/landmark closed-loop mileage is unavailable."
        )
    if archived_mileage.total_miles <= 0:
        raise RouteMileageUnavailable("Verified closed-loop mileage is invalid.")
    legs = (
        archived_mileage.leg_1_miles,
        archived_mileage.leg_2_miles,
        archived_mileage.leg_3_miles,
    )
    if any(leg is None or leg < 0 for leg in legs):
        raise RouteMileageUnavailable("Verified closed-loop route legs are incomplete.")
    # Rowland Heights is the operating base. A trip whose selected area is the
    # base itself legitimately has one zero-distance return/dispatch leg; it is
    # still a real, positive closed loop to the airport. Zero legs for every
    # other archive destination are treated as invalid rather than quoted.
    zero_leg_is_base_same_point = (
        archived_mileage.destination == "Rowland Heights"
        and sum(leg == 0 for leg in legs) == 1
        and sum(leg or Decimal("0") for leg in legs) > 0
    )
    if any(leg == 0 for leg in legs) and not zero_leg_is_base_same_point:
        raise RouteMileageUnavailable("Verified closed-loop route legs are incomplete.")
    return RouteMileage(
        total_miles=archived_mileage.total_miles,
        distance_meters=int(archived_mileage.total_miles * METERS_PER_MILE),
        pricing_source=CITY_MILEAGE_ARCHIVE_PRICING_SOURCE,
        reference_destination=archived_mileage.destination,
        leg_1_miles=archived_mileage.leg_1_miles,
        leg_2_miles=archived_mileage.leg_2_miles,
        leg_3_miles=archived_mileage.leg_3_miles,
    )


def get_round_trip_mileage(
    service_type: "QuoteServiceType",
    airport_code: "QuoteAirportCode",
    customer_location: str,
) -> RouteMileage:
    """Calculate Jason's complete driving loop in Google Maps Routes API.

    Airport pickup: base → airport → customer → base.
    Airport dropoff: base → customer → airport → base.
    """

    service_type_value = getattr(service_type, "value", service_type)
    airport_code_value = getattr(airport_code, "value", airport_code)
    try:
        return get_archived_round_trip_mileage(
            service_type=service_type,
            airport_code=airport_code,
            customer_location=customer_location,
        )
    except RouteMileageUnavailable:
        # This legacy helper may still serve internal routing integrations. The
        # Quote Estimate customer flow calls get_archived_round_trip_mileage
        # directly and therefore never reaches this dynamic fallback.
        pass

    api_key = settings.google_maps_api_key
    if not api_key:
        raise RouteMileageUnavailable("Road-mileage service is not configured.")

    airport = AIRPORT_ADDRESSES[airport_code_value]
    base = settings.jason_base_route_address
    stop_order = (
        [airport, customer_location]
        if service_type_value == "AIRPORT_PICKUP"
        else [customer_location, airport]
    )
    payload = {
        "origin": {"address": base},
        "destination": {"address": base},
        "intermediates": [{"address": stop} for stop in stop_order],
        "travelMode": "DRIVE",
        # Price is based on distance, so a stable non-traffic route is intentional.
        "routingPreference": "TRAFFIC_UNAWARE",
    }

    try:
        response = requests.post(
            GOOGLE_ROUTES_URL,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": "routes.distanceMeters,routes.legs.distanceMeters",
            },
            timeout=10,
        )
    except requests.RequestException as exc:
        raise RouteMileageUnavailable("Road-mileage service is unavailable.") from exc

    if not response.ok:
        raise RouteMileageUnavailable("Road-mileage service could not calculate this route.")

    try:
        routes = response.json()["routes"]
        route = routes[0]
        distance_meters = int(route["distanceMeters"])
        leg_distances = [int(leg["distanceMeters"]) for leg in route["legs"]]
    except (IndexError, KeyError, TypeError, ValueError) as exc:
        raise RouteMileageUnavailable("Road-mileage service returned no usable route.") from exc

    if distance_meters <= 0:
        raise RouteMileageUnavailable("Road-mileage service returned an invalid route.")
    if len(leg_distances) != 3 or any(distance <= 0 for distance in leg_distances):
        raise RouteMileageUnavailable("Road-mileage service returned incomplete route legs.")

    return RouteMileage(
        total_miles=Decimal(distance_meters) / METERS_PER_MILE,
        distance_meters=distance_meters,
        pricing_source=GOOGLE_ROUTES_PRICING_SOURCE,
        leg_1_miles=Decimal(leg_distances[0]) / METERS_PER_MILE,
        leg_2_miles=Decimal(leg_distances[1]) / METERS_PER_MILE,
        leg_3_miles=Decimal(leg_distances[2]) / METERS_PER_MILE,
    )


def price_range_for_miles(total_miles: Decimal) -> MileagePriceRange:
    """Apply Pricing Engine V1 to verified closed-loop road mileage."""

    if total_miles <= 0:
        raise ValueError("total_miles must be greater than zero")

    first_band = min(total_miles, MODEL_A_FIRST_BAND_MILES)
    second_band = min(
        max(total_miles - MODEL_A_FIRST_BAND_MILES, Decimal("0")),
        MODEL_A_SECOND_BAND_END_MILES - MODEL_A_FIRST_BAND_MILES,
    )
    long_band = max(total_miles - MODEL_A_SECOND_BAND_END_MILES, Decimal("0"))
    raw_midpoint = (
        MODEL_A_BASE_FARE
        + first_band * MODEL_A_FIRST_BAND_RATE
        + second_band * MODEL_A_SECOND_BAND_RATE
        + long_band * MODEL_A_LONG_BAND_RATE
    )
    rounded_midpoint = _round_to_nearest_five(raw_midpoint)
    half_width = max(Decimal("10"), rounded_midpoint * Decimal("0.10"))
    minimum = max(Decimal("0"), _round_to_nearest_five(rounded_midpoint - half_width))
    maximum = _round_to_nearest_five(rounded_midpoint + half_width)
    return MileagePriceRange(
        minimum_amount=minimum,
        maximum_amount=maximum,
        suggested_amount=rounded_midpoint,
        raw_midpoint=raw_midpoint,
        rounded_midpoint=rounded_midpoint,
        half_width=half_width,
    )


def _round_to_nearest_five(amount: Decimal) -> Decimal:
    """Round money to a customer-readable $5 increment, half up."""

    return (
        (amount / Decimal("5")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        * Decimal("5")
    )


def price_range_for_route(
    total_miles: Decimal,
    airport_code: str,
    reference_destination: str | None,
) -> MileagePriceRange:
    """Compatibility wrapper; all destinations use the same mileage formula."""

    del airport_code, reference_destination
    return price_range_for_miles(total_miles)
