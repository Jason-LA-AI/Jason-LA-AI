from decimal import Decimal

import pytest

from app.services.route_pricing import price_range_for_miles, price_range_for_route
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
