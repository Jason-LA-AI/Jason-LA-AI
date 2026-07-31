"""Internal pricing engine for Jason transportation quotes."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class PricingResult:
    """Internal pricing recommendation."""

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
) -> PricingResult:
    """
    Calculate an internal suggested price.

    Jason approval is always required.
    """

    factors: dict[str, str] = {}


    # LAX -> Rowland Heights

    if airport == "LAX" and destination == "Rowland Heights":

        return PricingResult(
            suggested_amount=Decimal("140"),
            minimum_amount=Decimal("130"),
            maximum_amount=Decimal("150"),
            pricing_source="pricing_rules.md",
            factors=factors,
        )


    # ONT -> Rowland Heights

    if airport == "ONT" and destination == "Rowland Heights":

        return PricingResult(
            suggested_amount=Decimal("70"),
            minimum_amount=Decimal("60"),
            maximum_amount=Decimal("80"),
            pricing_source="pricing_rules.md",
            factors=factors,
        )
    if airport == "ONT" and destination == "Irvine":

        return PricingResult(
            suggested_amount=Decimal("150"),
            minimum_amount=Decimal("140"),
            maximum_amount=Decimal("160"),
            pricing_source="pricing_rules.md",
            factors=factors,
        )


    # LAX -> Irvine

    if airport == "LAX" and destination == "Irvine":

        return PricingResult(
            suggested_amount=Decimal("170"),
            minimum_amount=Decimal("160"),
            maximum_amount=Decimal("180"),
            pricing_source="pricing_rules.md",
            factors=factors,
        )


    # LAX -> San Diego

    if airport == "LAX" and destination == "San Diego":

        return PricingResult(
            suggested_amount=Decimal("290"),
            minimum_amount=Decimal("260"),
            maximum_amount=Decimal("320"),
            pricing_source="pricing_rules.md",
            factors=factors,
        )


    # Airport -> Airport

    if airport == "ONT" and destination == "LAX":

        return PricingResult(
            suggested_amount=Decimal("140"),
            minimum_amount=Decimal("120"),
            maximum_amount=Decimal("160"),
            pricing_source="pricing_rules.md",
            factors=factors,
        )


    if airport == "LAX" and destination == "ONT":

        return PricingResult(
            suggested_amount=Decimal("140"),
            minimum_amount=Decimal("120"),
            maximum_amount=Decimal("160"),
            pricing_source="pricing_rules.md",
            factors=factors,
        )


    if airport == "SNA" and destination == "LAX":

        return PricingResult(
            suggested_amount=Decimal("140"),
            minimum_amount=Decimal("120"),
            maximum_amount=Decimal("160"),
            pricing_source="pricing_rules.md",
            factors=factors,
        )


    if airport == "BUR" and destination == "LAX":

        return PricingResult(
            suggested_amount=Decimal("120"),
            minimum_amount=Decimal("100"),
            maximum_amount=Decimal("140"),
            pricing_source="pricing_rules.md",
            factors=factors,
        )


    return PricingResult(
        suggested_amount=None,
        minimum_amount=None,
        maximum_amount=None,
        pricing_source="pricing_rules.md",
        factors={
            "reason": "Route requires Jason review"
        },
    )