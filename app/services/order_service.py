"""Order creation for accepted V2.1 quote requests."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.lead import Lead
from app.models.order import Order
from app.models.quote_estimate import QuoteEstimate


def create_order_from_quote_request(
    db: Session,
    customer: Customer,
    lead: Lead,
    quote_estimate: QuoteEstimate,
) -> Order:
    """Create one operational order from a validated quote estimate."""

    if quote_estimate.service_type == "AIRPORT_PICKUP":
        pickup_location = quote_estimate.airport_code
        pickup_city = None
        destination = quote_estimate.location_input
        destination_city = quote_estimate.normalized_city
    else:
        pickup_location = quote_estimate.location_input
        pickup_city = quote_estimate.normalized_city
        destination = quote_estimate.airport_code
        destination_city = None

    has_risk = bool(quote_estimate.risk_flags) or bool(
        quote_estimate.manual_review_reason
    )
    order = Order(
        customer_id=customer.id,
        lead_id=lead.id,
        quote_estimate_id=quote_estimate.id,
        status="WAITING_FOR_JASON_APPROVAL",
        intent=quote_estimate.service_type,
        service_date=quote_estimate.service_date,
        service_timezone=quote_estimate.service_timezone,
        airport_code=quote_estimate.airport_code,
        pickup_at=quote_estimate.service_datetime,
        flight_number=quote_estimate.flight_number,
        trip_direction="ONE_WAY",
        pickup_location=pickup_location,
        pickup_city=pickup_city,
        destination=destination,
        destination_city=destination_city,
        postal_code=quote_estimate.postal_code,
        pricing_zone=quote_estimate.pricing_zone,
        passenger_count=quote_estimate.passenger_count,
        passenger_count_is_minimum=quote_estimate.passenger_count_is_minimum,
        large_suitcase_count=quote_estimate.large_suitcase_count,
        large_suitcase_count_is_minimum=(
            quote_estimate.large_suitcase_count_is_minimum
        ),
        oversized_items_present=quote_estimate.oversized_items_present,
        child_seat_required=_child_seat_value(
            quote_estimate.child_seat_required
        ),
        vehicle_assessment=quote_estimate.vehicle_assessment,
        risk_level="HIGH" if has_risk else "LOW",
        risk_reason=quote_estimate.manual_review_reason,
    )
    db.add(order)
    db.flush()
    return order


def _child_seat_value(value: bool | str) -> str:
    """Convert boolean input while preserving the model's existing YES/NO values."""

    if isinstance(value, bool):
        return "YES" if value else "NO"
    return value
