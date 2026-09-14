"""Transactional outbox event creation without external delivery."""

from __future__ import annotations

from datetime import datetime, timezone
from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from app.models.approval import Approval
from app.models.customer import Customer
from app.models.order import Order
from app.models.outbox_event import OutboxEvent
from app.models.quote import Quote
from app.models.quote_estimate import QuoteEstimate


def create_outbox_event(
    db: Session,
    approval: Approval,
    order: Order,
    quote: Quote,
    customer: Customer,
    quote_estimate: QuoteEstimate,
    source: str,
    contact_information: Mapping[str, Any],
) -> OutboxEvent:
    """Store a pending quote-request event in the current transaction."""

    event = OutboxEvent(
        event_type="QUOTE_REQUEST_CREATED",
        aggregate_type="APPROVAL",
        aggregate_id=approval.id,
        payload={
            "approval_id": str(approval.id),
            "quote_id": str(quote.id),
            "order_id": str(order.id),
            "customer_id": str(customer.id),
            "estimate_id": str(quote_estimate.id),
            "route_summary": quote_estimate.route_summary,
            "service_type": quote_estimate.service_type,
            "customer_name": customer.display_name,
            "preferred_contact_method": contact_information.get("preferred_contact_method"),
            "phone": contact_information.get("phone"),
            "email": contact_information.get("email"),
            "wechat_id": contact_information.get("wechat_id"),
            "line_id": contact_information.get("line_id"),
            "source": source,
            "airport_code": quote_estimate.airport_code,
            "service_date": quote_estimate.service_date.isoformat(),
            "service_time": quote_estimate.service_time.isoformat(timespec="minutes"),
            "service_timezone": quote_estimate.service_timezone,
            "flight_number": quote_estimate.flight_number,
            "location_input": quote_estimate.location_input,
            "passenger_count": quote_estimate.passenger_count,
            "large_luggage_count": quote_estimate.large_suitcase_count,
            "child_seat_required": quote_estimate.child_seat_required,
            "oversized_items": quote_estimate.oversized_items_present,
            "suggested_amount": _amount_string(quote_estimate.suggested_amount),
            "estimated_min_amount": _amount_string(quote_estimate.estimated_min_amount),
            "estimated_max_amount": _amount_string(quote_estimate.estimated_max_amount),
            "currency_code": quote_estimate.currency_code,
            "pricing_source": quote_estimate.pricing_source,
            "pricing_status": quote_estimate.status,
            "manual_review_reason": quote_estimate.manual_review_reason,
        },
        status="PENDING",
        attempt_count=0,
        available_at=datetime.now(timezone.utc),
        processed_at=None,
        last_error=None,
    )
    db.add(event)
    db.flush()
    return event


def _amount_string(value: object | None) -> str | None:
    return str(value) if value is not None else None
