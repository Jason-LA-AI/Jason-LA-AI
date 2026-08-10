"""Mock Telegram delivery adapter for review notifications."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import object_session

from app.models.notification import Notification
from app.services.telegram_provider import TelegramProvider


NOT_SUPPORTED_CHANNEL = "NOT_SUPPORTED_CHANNEL"


def send_telegram_notification(
    notification: Notification,
) -> Notification | str:
    """Send one Telegram notification through the isolated mock provider."""

    if notification.channel != "TELEGRAM":
        return NOT_SUPPORTED_CHANNEL

    db = object_session(notification)
    if db is None:
        raise RuntimeError("Notification is not attached to a database session.")

    try:
        message = _render_quote_request_review(notification)
        result = TelegramProvider().send_message(message, reply_markup=None)

        notification.status = "SENT"
        notification.sent_at = datetime.now(timezone.utc)
        notification.provider = str(result["provider"])
        notification.provider_message_id = str(result["message_id"])
        notification.last_error = None
    except Exception as exc:
        notification.status = "FAILED"
        notification.attempt_count = (notification.attempt_count or 0) + 1
        notification.sent_at = None
        notification.last_error = str(exc)

    db.add(notification)
    db.flush()
    return notification


def _render_quote_request_review(notification: Notification) -> str:
    if notification.template_key != "QUOTE_REQUEST_REVIEW":
        raise ValueError(f"Unsupported Telegram template: {notification.template_key}")

    payload = notification.payload or {}
    return "\n".join(
        (
            "New quote request requires review",
            f"Approval ID: {_payload_value(payload, 'approval_id')}",
            f"Order ID: {_payload_value(payload, 'order_id')}",
            f"Quote ID: {_payload_value(payload, 'quote_id')}",
            f"Estimate ID: {_payload_value(payload, 'estimate_id')}",
            f"Service Type: {_payload_value(payload, 'service_type')}",
            f"Source: {payload.get('source') or 'UNKNOWN'}",
            f"Route Summary: {_payload_value(payload, 'route_summary')}",
        )
    )


def _payload_value(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if value is None:
        raise ValueError(f"Notification payload is missing {key}.")
    return str(value)
