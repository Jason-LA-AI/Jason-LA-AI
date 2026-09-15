from decimal import Decimal

import pytest

from app.services.route_pricing import price_range_for_miles


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
