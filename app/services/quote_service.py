"""Quote creation from persisted V2.1 quote estimates."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.quote import Quote
from app.models.quote_estimate import QuoteEstimate


def create_quote_from_quote_request(
    db: Session,
    order: Order,
    quote_estimate: QuoteEstimate,
) -> Quote:
    """Create a reviewable quote without recalculating estimate pricing."""

    is_priced_estimate = quote_estimate.status == "ESTIMATED"
    quote = Quote(
        order_id=order.id,
        version_number=1,
        quote_type="ONE_WAY",
        status="WAITING_FOR_JASON_APPROVAL",
        currency_code=quote_estimate.currency_code,
        suggested_min_amount=(
            quote_estimate.estimated_min_amount if is_priced_estimate else None
        ),
        suggested_max_amount=(
            quote_estimate.estimated_max_amount if is_priced_estimate else None
        ),
        suggested_amount=(
            quote_estimate.suggested_amount if is_priced_estimate else None
        ),
        pricing_source=quote_estimate.pricing_source,
        pricing_limitations=(
            quote_estimate.manual_review_reason
            if quote_estimate.status == "MANUAL_REVIEW_REQUIRED"
            else None
        ),
        additional_fee_factors=quote_estimate.pricing_factors,
        knowledge_version=quote_estimate.pricing_rule_version,
    )
    db.add(quote)
    db.flush()
    return quote
