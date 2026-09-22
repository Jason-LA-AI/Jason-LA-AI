from decimal import Decimal

import pytest

from unittest.mock import MagicMock

from app.services.route_pricing import (
    get_exact_address_round_trip_mileage,
    price_range_for_miles,
    price_range_for_route,
)
from app.services.pricing_engine import calculate_price


@pytest.mark.parametrize(
    ("miles", "raw_midpoint", "midpoint", "minimum", "maximum"),
    [
        ("50", "83.53", "85", "75", "95"),
        ("100", "128.53", "130", "115", "145"),
        ("200", "183.53", "185", "165", "205"),
    ],
)
def test_mileage_price_ranges_follow_pricing_engine_v1(
    miles: str,
    raw_midpoint: str,
    midpoint: str,
    minimum: str,
    maximum: str,
) -> None:
    quote = price_range_for_miles(Decimal(miles))

    assert quote.raw_midpoint == Decimal(raw_midpoint)
    assert quote.rounded_midpoint == Decimal(midpoint)
    assert quote.suggested_amount == Decimal(midpoint)
    assert quote.minimum_amount == Decimal(minimum)
    assert quote.maximum_amount == Decimal(maximum)


def test_every_destination_uses_the_same_mileage_formula() -> None:
    quote = price_range_for_route(Decimal("999"), "LAX", "Las Vegas")

    # No city-specific price table: only the continuous mileage formula applies.
    assert quote.raw_midpoint == Decimal("503.13")
    assert quote.minimum_amount == Decimal("455")
    assert quote.maximum_amount == Decimal("555")


def test_rounding_keeps_an_exact_five_dollar_midpoint() -> None:
    # 68.3 miles produces exactly $100.00 before display rounding.
    quote = price_range_for_miles(Decimal("68.3"))

    assert quote.raw_midpoint == Decimal("100.00")
    assert quote.rounded_midpoint == Decimal("100")


def test_midpoint_between_five_dollar_increments_rounds_half_up() -> None:
    quote = price_range_for_miles(Decimal("45"))

    assert quote.raw_midpoint == Decimal("78.53")
    assert quote.rounded_midpoint == Decimal("80")


def test_range_uses_ten_dollars_when_ten_percent_is_smaller() -> None:
    quote = price_range_for_miles(Decimal("46.0"))

    assert quote.rounded_midpoint == Decimal("80")
    assert quote.half_width == Decimal("10")
    assert (quote.minimum_amount, quote.maximum_amount) == (
        Decimal("70"),
        Decimal("90"),
    )


def test_range_uses_percentage_when_it_is_larger_than_ten_dollars() -> None:
    quote = price_range_for_miles(Decimal("247.5"))

    assert quote.rounded_midpoint == Decimal("205")
    assert quote.half_width == Decimal("20.50")
    assert (quote.minimum_amount, quote.maximum_amount) == (
        Decimal("185"),
        Decimal("225"),
    )


def test_range_endpoints_are_nearest_five_and_never_negative() -> None:
    quote = price_range_for_miles(Decimal("0.01"))

    assert quote.minimum_amount >= 0
    assert quote.minimum_amount % 5 == 0
    assert quote.maximum_amount % 5 == 0


def test_legacy_customer_entry_point_requires_an_explicit_service_direction() -> None:
    review = calculate_price("LAX", "Chino")
    pickup = calculate_price("LAX", "Chino", service_type="AIRPORT_PICKUP")
    dropoff = calculate_price("LAX", "Chino", service_type="AIRPORT_DROPOFF")

    assert review.minimum_amount is None
    assert review.pricing_source == "route_mileage_unavailable"
    assert pickup.factors["total_road_miles"] == "104.0"
    assert dropoff.factors["total_road_miles"] == "103.5"


def test_exact_address_provider_geocodes_then_routes_three_road_legs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.route_pricing.settings.google_maps_api_key", "test-key")
    geocode = MagicMock(ok=True)
    geocode.json.return_value = {
        "status": "OK",
        "results": [{"formatted_address": "13820 Schleisman Rd, Eastvale, CA 92880, USA", "place_id": "place-id", "types": ["street_address"], "geometry": {"location": {"lat": 33.97, "lng": -117.56}}, "address_components": [
            {"long_name": "Eastvale", "types": ["locality"]}, {"long_name": "California", "types": ["administrative_area_level_1"]}, {"long_name": "92880", "types": ["postal_code"]}, {"long_name": "United States", "types": ["country"]}
        ]}],
    }
    route = MagicMock(ok=True)
    route.json.return_value = {"routes": [{"distanceMeters": 193121, "legs": [{"distanceMeters": 48280}, {"distanceMeters": 96561}, {"distanceMeters": 48280}]}]}
    monkeypatch.setattr("app.services.route_pricing.requests.get", lambda *_args, **_kwargs: geocode)
    monkeypatch.setattr("app.services.route_pricing.requests.post", lambda *_args, **_kwargs: route)
    address, mileage = get_exact_address_round_trip_mileage("AIRPORT_PICKUP", "LAX", "13820 Schleisman Rd, Eastvale, CA 92880")
    assert address.city == "Eastvale"
    assert address.place_id == "place-id"
    assert mileage.pricing_source == "google_routes_exact_address_v1"
    assert (mileage.leg_1_miles, mileage.leg_2_miles, mileage.leg_3_miles) == pytest.approx((Decimal("30"), Decimal("60"), Decimal("30")), rel=Decimal("0.01"))
