"""Transactional business processing for approval action tokens."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.approval import Approval
from app.models.quote import Quote
from app.services.approval_action_service import validate_approval_action_token


APPROVAL_NOT_PROCESSABLE = "APPROVAL_NOT_PROCESSABLE"


class ApprovalActionProcessorError(Exception):
    """Business error raised when an approval cannot accept an action."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def process_approval_action(
    db: Session,
    token: str,
    actor: str,
) -> Approval:
    """Apply one validated action without committing or sending notifications."""

    token_record = validate_approval_action_token(db, token)
    approval = db.scalar(
        select(Approval)
        .where(Approval.id == token_record.approval_id)
        .with_for_update()
    )
    if approval is None or approval.status != "PENDING":
        raise ApprovalActionProcessorError(APPROVAL_NOT_PROCESSABLE)

    quote = None
    if approval.quote_id is not None:
        quote = db.get(Quote, approval.quote_id)
        if quote is None:
            raise RuntimeError("Approval quote was not found.")

    decided_at = datetime.now(timezone.utc)
    approval.status = "APPROVED" if token_record.action == "APPROVE" else "DECLINED"
    approval.decision_by = actor
    approval.decided_at = decided_at
    approval.decision_value = {"action": token_record.action}

    if quote is not None:
        quote.status = approval.status
        db.add(quote)

    token_record.status = "USED"
    token_record.used_at = decided_at

    db.add(approval)
    db.add(token_record)
    db.flush()
    return approval
