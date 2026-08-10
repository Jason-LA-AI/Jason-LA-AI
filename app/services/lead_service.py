"""Lead creation for accepted V2.1 quote requests."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.lead import Lead
from app.models.quote_estimate import QuoteEstimate


def create_lead_from_quote_request(
    db: Session,
    customer: Customer,
    quote_estimate: QuoteEstimate,
    customer_contact_information: Mapping[str, Any],
    source: str,
) -> Lead:
    """Create a website lead linked to the customer for an accepted estimate."""

    # Contact details remain on Customer and are intentionally not copied to Lead.
    del customer_contact_information

    accepted_at = datetime.now(timezone.utc)
    lead = Lead(
        customer_id=customer.id,
        source=source,
        intent=quote_estimate.service_type,
        status="PENDING_JASON",
        received_at=accepted_at,
        next_action="REVIEW_QUOTE_REQUEST",
        next_action_owner="JASON",
        intake_method="STRUCTURED_QUOTE_V2",
        estimate_accepted_at=accepted_at,
    )
    db.add(lead)
    db.flush()
    return lead
