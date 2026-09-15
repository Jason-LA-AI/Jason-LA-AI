from decimal import Decimal

import pytest

from app.services.route_pricing import price_range_for_miles, price_range_for_route


@pytest.mark.parametrize(
    ("miles", "minimum", "maximum"),
    [
        ("50", "80", "80"),
        ("100", "100", "150"),
        ("200", "200", "300"),
    ],
)
def test_mileage_price_ranges_follow_jason_rule(
    miles: str, minimum: str, maximum: str
) -> None:
    quote = price_range_for_miles(Decimal(miles))

    assert quote.minimum_amount == Decimal(minimum)
    assert quote.maximum_amount == Decimal(maximum)


@pytest.mark.parametrize(
    ("destination", "minimum", "maximum"),
    [
        ("Las Vegas", "450", "600"),
        ("UC San Diego", "240", "300"),
        ("San Francisco", "850", "1000"),
    ],
)
def test_confirmed_lax_long_distance_ranges_are_not_mileage_bands(
    destination: str, minimum: str, maximum: str
) -> None:
    quote = price_range_for_route(Decimal("999"), "LAX", destination)

    assert quote.minimum_amount == Decimal(minimum)
    assert quote.maximum_amount == Decimal(maximum)


def test_confirmed_ranges_do_not_apply_to_a_different_airport() -> None:
    quote = price_range_for_route(Decimal("500"), "ONT", "Las Vegas")

    assert quote.minimum_amount == Decimal("500")
    assert quote.maximum_amount == Decimal("750")
