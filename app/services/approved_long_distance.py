"""Explicit, direction-scoped long-distance fare approvals.

These are Jason-approved preliminary customer ranges.  They intentionally sit
outside Pricing Engine V1 and never imply that a reverse route or another
airport has the same fare.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


APPROVED_LONG_DISTANCE_PRICING_SOURCE = "approved_long_distance_range_v1"
APPROVED_LONG_DISTANCE_PRICING_RULE_VERSION = "approved_long_distance_v1"


@dataclass(frozen=True)
class ApprovedLongDistanceRange:
    minimum_amount: Decimal
    maximum_amount: Decimal

    @property
    def suggested_amount(self) -> Decimal:
        return (self.minimum_amount + self.maximum_amount) / Decimal("2")


_APPROVED_ROUTE_RANGES = {
    # These keys deliberately include the direction.  A range is a commercial
    # authorization for one route, never an inference about its reverse.
    ("LAX", "AIRPORT_PICKUP", "Las Vegas"): ("500", "750"),
    ("LAX", "AIRPORT_PICKUP", "San Francisco"): ("850", "1000"),
    ("LAX", "AIRPORT_PICKUP", "San Diego"): ("240", "280"),
    ("LAX", "AIRPORT_PICKUP", "Santa Barbara"): ("220", "260"),
    ("LAX", "AIRPORT_DROPOFF", "San Diego"): ("240", "280"),
}


def approved_long_distance_range(
    *, service_type: str, airport_code: str, destination: str
) -> ApprovedLongDistanceRange | None:
    """Return an approval only for its exact airport, direction, and city."""

    amounts = _APPROVED_ROUTE_RANGES.get((airport_code, service_type, destination))
    if amounts is None:
        return None
    return ApprovedLongDistanceRange(*(Decimal(amount) for amount in amounts))


def is_approved_long_distance_destination(destination: str) -> bool:
    """Whether a destination is approval-scoped rather than V1-scoped."""

    return any(route_destination == destination for _, _, route_destination in _APPROVED_ROUTE_RANGES)
