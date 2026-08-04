"""Validated database lookup for persisted V2.1 quote estimates."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.quote_estimate import QuoteEstimate


ESTIMATE_NOT_FOUND = "ESTIMATE_NOT_FOUND"
ESTIMATE_NOT_AVAILABLE = "ESTIMATE_NOT_AVAILABLE"
ESTIMATE_EXPIRED = "ESTIMATE_EXPIRED"

AVAILABLE_ESTIMATE_STATUSES = frozenset(
    {
        "ESTIMATED",
        "MANUAL_REVIEW_REQUIRED",
    }
)


class QuoteEstimateLookupError(Exception):
    """Business error raised when an estimate cannot be used."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def get_valid_quote_estimate(
    db: Session,
    estimate_id: UUID,
) -> QuoteEstimate:
    """Return an available, unexpired persisted estimate by primary key."""

    estimate = db.get(QuoteEstimate, estimate_id)
    if estimate is None:
        raise QuoteEstimateLookupError(ESTIMATE_NOT_FOUND)

    if estimate.status not in AVAILABLE_ESTIMATE_STATUSES:
        raise QuoteEstimateLookupError(ESTIMATE_NOT_AVAILABLE)

    expires_at = estimate.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < datetime.now(timezone.utc):
        raise QuoteEstimateLookupError(ESTIMATE_EXPIRED)

    return estimate
