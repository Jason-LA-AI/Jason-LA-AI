"""Notification persistence without external delivery."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.notification import Notification


def create_notification(
    db: Session,
    *,
    channel: str,
    template_key: str,
    payload: dict[str, Any],
    approval_id: UUID | None = None,
    order_id: UUID | None = None,
    quote_id: UUID | None = None,
    recipient: str | None = None,
) -> Notification:
    """Create a pending notification in the caller's transaction."""

    notification = Notification(
        channel=channel,
        status="PENDING",
        template_key=template_key,
        recipient=recipient,
        approval_id=approval_id,
        order_id=order_id,
        quote_id=quote_id,
        payload=payload,
        provider=None,
        provider_message_id=None,
        attempt_count=0,
        last_error=None,
        sent_at=None,
    )
    db.add(notification)
    db.flush()
    return notification
