"""Transactional outbox event creation without external delivery."""

from __future__ import annotations

from datetime import datetime, timezone

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
            "source": source,
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
