"""Road-mileage lookup and mileage-based quote rules."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_UP
from typing import TYPE_CHECKING

import requests

from app.config.settings import settings

if TYPE_CHECKING:
    from app.schemas.quote_estimate import QuoteAirportCode, QuoteServiceType


GOOGLE_ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
METERS_PER_MILE = Decimal("1609.344")
MINIMUM_FARE = Decimal("80")
LOW_RATE_PER_MILE = Decimal("1.00")
HIGH_RATE_PER_MILE = Decimal("1.50")

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


@dataclass(frozen=True)
class MileagePriceRange:
    """The public planning range derived solely from total road miles."""

    minimum_amount: Decimal
    maximum_amount: Decimal
    suggested_amount: Decimal


def get_round_trip_mileage(
    service_type: "QuoteServiceType",
    airport_code: "QuoteAirportCode",
    customer_location: str,
) -> RouteMileage:
    """Calculate Jason's complete driving loop in Google Maps Routes API.

    Airport pickup: base → airport → customer → base.
    Airport dropoff: base → customer → airport → base.
    """

    api_key = settings.google_maps_api_key
    if not api_key:
        raise RouteMileageUnavailable("Road-mileage service is not configured.")

    airport = AIRPORT_ADDRESSES[airport_code.value]
    base = settings.jason_base_route_address
    stop_order = (
        [airport, customer_location]
        if service_type.value == "AIRPORT_PICKUP"
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
                "X-Goog-FieldMask": "routes.distanceMeters",
            },
            timeout=10,
        )
    except requests.RequestException as exc:
        raise RouteMileageUnavailable("Road-mileage service is unavailable.") from exc

    if not response.ok:
        raise RouteMileageUnavailable("Road-mileage service could not calculate this route.")

    try:
        routes = response.json()["routes"]
        distance_meters = int(routes[0]["distanceMeters"])
    except (IndexError, KeyError, TypeError, ValueError) as exc:
        raise RouteMileageUnavailable("Road-mileage service returned no usable route.") from exc

    if distance_meters <= 0:
        raise RouteMileageUnavailable("Road-mileage service returned an invalid route.")

    return RouteMileage(
        total_miles=Decimal(distance_meters) / METERS_PER_MILE,
        distance_meters=distance_meters,
    )


def price_range_for_miles(total_miles: Decimal) -> MileagePriceRange:
    """Apply Jason's $80 minimum and $1.00–$1.50 per road-mile rule."""

    if total_miles <= 0:
        raise ValueError("total_miles must be greater than zero")

    minimum = max(MINIMUM_FARE, total_miles * LOW_RATE_PER_MILE)
    maximum = max(MINIMUM_FARE, total_miles * HIGH_RATE_PER_MILE)
    # A quote never rounds down below the mileage rule.
    minimum = minimum.quantize(Decimal("1"), rounding=ROUND_UP)
    maximum = maximum.quantize(Decimal("1"), rounding=ROUND_UP)
    return MileagePriceRange(
        minimum_amount=minimum,
        maximum_amount=maximum,
        suggested_amount=(minimum + maximum) / Decimal("2"),
    )
