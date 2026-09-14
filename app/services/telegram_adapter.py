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
    service_type = _payload_value(payload, "service_type")
    airport = _optional_value(payload, "airport_code")
    location = _optional_value(payload, "location_input")
    route_lines = (
        (f"Pickup: {airport}", f"Drop-off: {location}")
        if service_type == "AIRPORT_PICKUP"
        else (f"Pickup: {location}", f"Drop-off: {airport}")
    )
    lines = [
        "New quote request requires review",
        f"Approval ID: {_payload_value(payload, 'approval_id')}",
        f"Order ID: {_payload_value(payload, 'order_id')}",
        f"Quote ID: {_payload_value(payload, 'quote_id')}",
        f"Estimate ID: {_payload_value(payload, 'estimate_id')}",
        f"Customer: {payload.get('customer_name') or 'Not provided'}",
        f"Preferred Contact: {payload.get('preferred_contact_method') or 'Not specified'}",
        *_contact_lines(payload),
        "",
        f"Service Type: {service_type}",
        f"Route: {_payload_value(payload, 'route_summary')}",
        f"Airport: {airport}",
        *route_lines,
        f"Date: {_optional_value(payload, 'service_date')}",
        f"Time: {_optional_value(payload, 'service_time')} {_optional_value(payload, 'service_timezone')}",
        f"Passengers: {_optional_value(payload, 'passenger_count')}",
        f"Large Luggage: {_optional_value(payload, 'large_luggage_count')}",
        f"Child Seat: {_yes_no(_optional_value(payload, 'child_seat_required'))}",
        f"Oversized Items: {_yes_no(_optional_value(payload, 'oversized_items'))}",
        f"Source: {payload.get('source') or 'UNKNOWN'}",
    ]
    if payload.get("flight_number"):
        lines.append(f"Flight Number: {payload['flight_number']}")
    lines.extend(("", *_pricing_recommendation_lines(payload)))
    return "\n".join(lines)


def _payload_value(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if value is None:
        raise ValueError(f"Notification payload is missing {key}.")
    return str(value)


def _optional_value(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    return str(value) if value is not None else "Not provided"


def _contact_lines(payload: dict[str, Any]) -> tuple[str, ...]:
    labels = (("phone", "Phone"), ("email", "Email"), ("wechat_id", "WeChat"), ("line_id", "LINE"))
    return tuple(f"{label}: {payload[key]}" for key, label in labels if payload.get(key))


def _yes_no(value: str) -> str:
    return "Yes" if str(value).upper() in {"YES", "TRUE"} else "No" if str(value).upper() in {"NO", "FALSE"} else value


def _pricing_recommendation_lines(payload: dict[str, Any]) -> tuple[str, ...]:
    suggested = payload.get("suggested_amount")
    minimum = payload.get("estimated_min_amount")
    maximum = payload.get("estimated_max_amount")
    source = payload.get("pricing_source") or "Not provided"
    status = payload.get("pricing_status") or "MANUAL_REVIEW_REQUIRED"
    lines = [
        "Pricing Recommendation:",
        f"Suggested Amount: {suggested if suggested is not None else 'Not available'}",
        f"Range: {f'{minimum} - {maximum}' if minimum is not None and maximum is not None else 'Not available'}",
        f"Currency: {payload.get('currency_code') or 'USD'}",
        f"Pricing Source: {source}",
        f"Pricing Status: {status}",
    ]
    if suggested is None or minimum is None or maximum is None:
        lines.insert(1, "Manual Review Required")
    if payload.get("manual_review_reason"):
        lines.append(f"Manual Review Reason: {payload['manual_review_reason']}")
    return tuple(lines)
