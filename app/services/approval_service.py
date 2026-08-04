"""Approval creation for V2.1 quote requests awaiting Jason review."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.approval import Approval
from app.models.order import Order
from app.models.quote import Quote
from app.models.quote_estimate import QuoteEstimate


def create_approval_from_quote_request(
    db: Session,
    order: Order,
    quote: Quote,
    quote_estimate: QuoteEstimate,
) -> Approval:
    """Create a pending final-price approval without sending notifications."""

    is_priced_estimate = quote_estimate.status == "ESTIMATED"
    approval = Approval(
        order_id=order.id,
        quote_id=quote.id,
        approval_type="FINAL_PRICE",
        status="PENDING",
        requested_by="SYSTEM",
        requested_at=datetime.now(timezone.utc),
        request_summary=_request_summary(quote_estimate),
        proposed_value={
            "currency_code": quote_estimate.currency_code,
            "estimated_min_amount": _amount_string(
                quote_estimate.estimated_min_amount
            ) if is_priced_estimate else None,
            "estimated_max_amount": _amount_string(
                quote_estimate.estimated_max_amount
            ) if is_priced_estimate else None,
            "suggested_amount": _amount_string(
                quote_estimate.suggested_amount
            ) if is_priced_estimate else None,
            "vehicle_assessment": quote_estimate.vehicle_assessment,
            "risk_flags": quote_estimate.risk_flags,
            "requires_jason_review": quote_estimate.requires_jason_review,
        },
        decision_by=None,
        decided_at=None,
        decision_value=None,
        decision_note=None,
    )
    db.add(approval)
    db.flush()
    return approval


def _request_summary(quote_estimate: QuoteEstimate) -> str:
    service_name = quote_estimate.service_type.replace("_", " ").title()
    service_time = quote_estimate.service_time.strftime("%H:%M")
    child_seat = _yes_no(quote_estimate.child_seat_required)
    oversized_items = _yes_no(quote_estimate.oversized_items_present)
    risk = _risk_summary(quote_estimate)

    return "\n".join(
        (
            service_name,
            quote_estimate.route_summary,
            f"{quote_estimate.service_date.isoformat()} {service_time} "
            f"{quote_estimate.service_timezone}",
            "",
            "Passengers:",
            str(quote_estimate.passenger_count),
            "",
            "Large luggage:",
            str(quote_estimate.large_suitcase_count),
            "",
            "Child seat:",
            child_seat,
            "",
            "Oversized items:",
            oversized_items,
            "",
            "Vehicle:",
            quote_estimate.vehicle_assessment,
            "",
            "Risk:",
            risk,
        )
    )


def _amount_string(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _yes_no(value: bool | str) -> str:
    if isinstance(value, bool):
        return "YES" if value else "NO"
    return value


def _risk_summary(quote_estimate: QuoteEstimate) -> str:
    details = list(quote_estimate.risk_flags or [])
    if quote_estimate.manual_review_reason:
        details.append(quote_estimate.manual_review_reason)
    return "; ".join(details) if details else "None"
