"""Transactional worker logic for pending outbox events."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, object_session

from app.models.outbox_event import OutboxEvent
from app.services.notification_service import create_notification


OUTBOX_EVENT_NOT_FOUND = "OUTBOX_EVENT_NOT_FOUND"
OUTBOX_EVENT_NOT_PROCESSABLE = "OUTBOX_EVENT_NOT_PROCESSABLE"

PROCESSABLE_STATUSES = frozenset({"PENDING", "FAILED"})


class OutboxWorkerError(Exception):
    """Business error raised when an outbox event cannot be processed."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def process_pending_outbox_event(
    db: Session,
    event_id: UUID,
) -> OutboxEvent:
    """Lock and process one outbox event without committing the transaction."""

    statement = (
        select(OutboxEvent)
        .where(OutboxEvent.id == event_id)
        .with_for_update()
    )
    event = db.scalar(statement)
    if event is None:
        raise OutboxWorkerError(OUTBOX_EVENT_NOT_FOUND)
    if event.status not in PROCESSABLE_STATUSES:
        raise OutboxWorkerError(OUTBOX_EVENT_NOT_PROCESSABLE)

    event.status = "PROCESSING"
    db.flush()

    try:
        handled = handle_outbox_event(event)
        if handled is not True:
            raise RuntimeError("Outbox event handler did not complete successfully.")
    except Exception as exc:
        event.status = "FAILED"
        event.attempt_count = (event.attempt_count or 0) + 1
        event.processed_at = None
        event.last_error = str(exc)
        db.flush()
        return event

    event.status = "PROCESSED"
    event.processed_at = datetime.now(timezone.utc)
    event.last_error = None
    db.flush()
    return event


def handle_outbox_event(event: OutboxEvent) -> bool:
    """Run internal event handling; external delivery is intentionally absent."""

    if event.event_type != "QUOTE_REQUEST_CREATED":
        return True

    db = object_session(event)
    if db is None:
        raise RuntimeError("Outbox event is not attached to a database session.")

    payload = event.payload or {}
    notification_payload = {
        "approval_id": str(event.aggregate_id),
        "quote_id": _payload_string(payload, "quote_id"),
        "order_id": _payload_string(payload, "order_id"),
        "customer_id": _payload_string(payload, "customer_id"),
        "estimate_id": _payload_string(payload, "estimate_id"),
        "route_summary": payload.get("route_summary"),
        "service_type": payload.get("service_type"),
    }
    with db.begin_nested():
        create_notification(
            db,
            channel="TELEGRAM",
            template_key="QUOTE_REQUEST_REVIEW",
            payload=notification_payload,
            approval_id=event.aggregate_id,
            order_id=UUID(notification_payload["order_id"]),
            quote_id=UUID(notification_payload["quote_id"]),
            recipient=None,
        )
    return True


def _payload_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if value is None:
        raise ValueError(f"Outbox payload is missing {key}.")
    return str(value)
