"""Transactional orchestration for accepted V2.1 quote estimates."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.schemas.quote_request import (
    PreferredContactMethod,
    QuoteRequestCreate,
)
from app.services.approval_service import create_approval_from_quote_request
from app.services.customer_service import create_or_match_customer
from app.services.quote_estimate_lookup import get_valid_quote_estimate
from app.services.lead_service import create_lead_from_quote_request
from app.services.order_service import create_order_from_quote_request
from app.services.outbox_service import create_outbox_event
from app.services.quote_service import create_quote_from_quote_request
from app.services.telegram_notifier import send_approval_notification


CONTACT_METHOD_REQUIRED = "CONTACT_METHOD_REQUIRED"
PHONE_REQUIRED_FOR_SMS = "PHONE_REQUIRED_FOR_SMS"
EMAIL_REQUIRED_FOR_EMAIL = "EMAIL_REQUIRED_FOR_EMAIL"
WECHAT_REQUIRED = "WECHAT_REQUIRED"
LINE_REQUIRED = "LINE_REQUIRED"


class QuoteRequestError(Exception):
    """Business error raised when quote-request contact details are invalid."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class QuoteRequestProcessed(BaseModel):
    """Identifiers created by a successfully committed quote request."""

    quote_request_status: Literal["PENDING_JASON_REVIEW"] = "PENDING_JASON_REVIEW"
    customer_id: UUID
    lead_id: UUID
    order_id: UUID
    quote_id: UUID
    approval_id: UUID
    estimate_id: UUID


def process_quote_request(
    db: Session,
    request: QuoteRequestCreate,
) -> QuoteRequestProcessed:
    """Create and commit the complete quote-request business graph atomically."""

    try:
        estimate = get_valid_quote_estimate(db, request.estimate_id)
        phone, email, wechat_id, line_id, contact_method = _resolve_contact(request)
        source = _source_for_request(request)

        customer = create_or_match_customer(
            db,
            customer_name=request.customer_name,
            phone=phone,
            email=email,
            wechat_id=wechat_id,
            line_id=line_id,
            preferred_contact_method=contact_method,
            source=source,
        )
        lead = create_lead_from_quote_request(
            db,
            customer=customer,
            quote_estimate=estimate,
            customer_contact_information={
                "phone": phone,
                "email": email,
                "wechat_id": wechat_id,
                "line_id": line_id,
                "preferred_contact_method": contact_method.value,
            },
            source=source,
        )
        order = create_order_from_quote_request(
            db,
            customer=customer,
            lead=lead,
            quote_estimate=estimate,
        )
        quote = create_quote_from_quote_request(
            db,
            order=order,
            quote_estimate=estimate,
        )
        approval = create_approval_from_quote_request(
            db,
            order=order,
            quote=quote,
            quote_estimate=estimate,
        )
        create_outbox_event(
            db,
            approval=approval,
            order=order,
            quote=quote,
            customer=customer,
            quote_estimate=estimate,
            source=source,
            contact_information={
                "phone": phone,
                "email": email,
                "wechat_id": wechat_id,
                "line_id": line_id,
                "preferred_contact_method": contact_method.value,
            },
        )
        result = QuoteRequestProcessed(
            customer_id=customer.id,
            lead_id=lead.id,
            order_id=order.id,
            quote_id=quote.id,
            approval_id=approval.id,
            estimate_id=estimate.id,
        )
        db.commit()
        try:
            send_approval_notification(
                str(approval.id),
                _telegram_review_text(
                    estimate=estimate,
                    customer_name=customer.display_name,
                    source=source,
                    phone=phone,
                    email=email,
                    wechat_id=wechat_id,
                    line_id=line_id,
                    preferred_contact_method=contact_method.value,
                ),
            )
        except Exception:
            # The booking is already safely committed; notification delivery must
            # never turn a successful customer request into an error response.
            pass
        return result
    except Exception:
        db.rollback()
        raise


def accept_quote_request(
    db: Session,
    request: QuoteRequestCreate,
) -> QuoteRequestProcessed:
    """Backward-compatible alias for the transactional orchestrator."""

    return process_quote_request(db, request)


def _resolve_contact(
    request: QuoteRequestCreate,
) -> tuple[str | None, str | None, str | None, str | None, PreferredContactMethod]:
    """Validate one reachable channel and infer its method when not selected."""

    phone = request.phone.strip() if request.phone else None
    email = str(request.email) if request.email else None
    wechat_id = request.wechat_id.strip() if request.wechat_id else None
    line_id = request.line_id.strip() if request.line_id else None

    if not any((phone, email, wechat_id, line_id)):
        raise QuoteRequestError(CONTACT_METHOD_REQUIRED)

    contact_method = request.preferred_contact_method or _infer_contact_method(
        phone=phone,
        email=email,
        wechat_id=wechat_id,
        line_id=line_id,
    )
    required_value = {
        PreferredContactMethod.SMS: phone,
        PreferredContactMethod.EMAIL: email,
        PreferredContactMethod.WECHAT: wechat_id,
        PreferredContactMethod.LINE: line_id,
    }[contact_method]
    if required_value:
        return phone, email, wechat_id, line_id, contact_method

    error_code = {
        PreferredContactMethod.SMS: PHONE_REQUIRED_FOR_SMS,
        PreferredContactMethod.EMAIL: EMAIL_REQUIRED_FOR_EMAIL,
        PreferredContactMethod.WECHAT: WECHAT_REQUIRED,
        PreferredContactMethod.LINE: LINE_REQUIRED,
    }[contact_method]
    raise QuoteRequestError(error_code)


def _infer_contact_method(
    *,
    phone: str | None,
    email: str | None,
    wechat_id: str | None,
    line_id: str | None,
) -> PreferredContactMethod:
    if phone:
        return PreferredContactMethod.SMS
    if email:
        return PreferredContactMethod.EMAIL
    if wechat_id:
        return PreferredContactMethod.WECHAT
    if line_id:
        return PreferredContactMethod.LINE
    raise QuoteRequestError(CONTACT_METHOD_REQUIRED)


def _source_for_request(request: QuoteRequestCreate) -> str:
    """Preserve the required stored source while making form attribution optional."""

    return request.source.value if request.source else "UNKNOWN"


def _pricing_recommendation_text(estimate: object) -> str:
    source = getattr(estimate, "pricing_source", None) or "Not provided"
    status_value = getattr(estimate, "status", None) or "MANUAL_REVIEW_REQUIRED"
    suggested = getattr(estimate, "suggested_amount", None)
    minimum = getattr(estimate, "estimated_min_amount", None)
    maximum = getattr(estimate, "estimated_max_amount", None)
    currency = getattr(estimate, "currency_code", None) or "USD"
    factors = getattr(estimate, "pricing_factors", None)
    if isinstance(factors, dict) and factors.get("exact_address_route"):
        return "\n".join(
            line for line in (
                "APPROVED LONG-DISTANCE RANGE · EXACT ADDRESS ROUTE" if factors.get("approved_long_distance_range") else "EXACT ADDRESS ROUTE",
                *((f"Route: {factors.get('approved_route', 'Not available')}", f"Direction: {factors.get('approved_direction', 'Not available')}") if factors.get("approved_long_distance_range") else ()),
                f"Exact address: {factors.get('normalized_address', 'Not available')}",
                f"City: {factors.get('geocoded_city', 'Not available')}",
                f"Geocode source: {factors.get('geocode_source', 'Not available')}",
                f"Route source: {factors.get('route_source', 'Not available')}",
                f"Leg 1: {factors.get('leg_1_road_miles', 'Not available')} mi",
                f"Leg 2: {factors.get('leg_2_road_miles', 'Not available')} mi",
                f"Leg 3: {factors.get('leg_3_road_miles', 'Not available')} mi",
                f"Closed-loop mileage: {factors.get('total_road_miles', 'Not available')} mi",
                f"Customer range: {factors.get('customer_range') or factors.get('approved_customer_range', 'Not available')}",
                f"Pricing source: {source}",
            )
        )
    if isinstance(factors, dict) and factors.get("approved_long_distance_range"):
        return "\n".join((
            "APPROVED LONG-DISTANCE RANGE",
            f"Route: {factors.get('approved_route', 'Not available')}",
            f"Direction: {factors.get('approved_direction', 'Not available')}",
            f"Closed-loop mileage: {factors.get('total_road_miles', 'Not available')} mi",
            f"Approved customer range: {factors.get('approved_customer_range', 'Not available')}",
            f"Pricing source: {source}",
        ))
    if isinstance(factors, dict) and factors.get("not_for_quoting"):
        lines = [
            "LONG_DISTANCE_REVIEW_REQUIRED",
            f"Closed-loop mileage: {factors.get('total_road_miles', 'Not available')} mi",
            "Pricing V1 diagnostic only: "
            f"${factors.get('raw_model_min', 'Not available')}–${factors.get('raw_model_max', 'Not available')}",
            "Do not use automatic fare.",
            "Jason must review manually.",
        ]
        reason = getattr(estimate, "manual_review_reason", None)
        if reason:
            lines.append(f"Manual Review Reason: {reason}")
        return "\n".join(lines)
    lines = ["Pricing Recommendation:"]
    if suggested is None or minimum is None or maximum is None:
        lines.append("Manual Review Required")
    lines.extend((
        f"Suggested Amount: {suggested if suggested is not None else 'Not available'}",
        f"Range: {f'{minimum} - {maximum}' if minimum is not None and maximum is not None else 'Not available'}",
        f"Currency: {currency}",
        f"Pricing Source: {source}",
        f"Pricing Status: {status_value}",
    ))
    reason = getattr(estimate, "manual_review_reason", None)
    if reason:
        lines.append(f"Manual Review Reason: {reason}")
    lines.extend(_pricing_diagnostic_lines(factors))
    return "\n".join(lines)


def _pricing_diagnostic_lines(factors: object) -> tuple[str, ...]:
    """Keep V1 archive mileage diagnostics in Jason's internal review text."""

    if not isinstance(factors, dict):
        return ()
    labels = (
        ("total_road_miles", "Closed-loop Miles"),
        ("raw_midpoint", "Raw Midpoint"),
        ("rounded_midpoint", "Rounded Midpoint"),
        ("customer_range", "Customer Range"),
        ("pricing_rule_version", "Pricing Rule"),
        ("location_source", "Location Source"),
        ("mileage_source", "Mileage Source"),
    )
    return tuple(f"{label}: {factors[key]}" for key, label in labels if factors.get(key) is not None)


def _telegram_review_text(
    *,
    estimate: object,
    customer_name: str,
    source: str,
    phone: str | None,
    email: str | None,
    wechat_id: str | None,
    line_id: str | None,
    preferred_contact_method: str,
) -> str:
    """Render the real internal Telegram alert from persisted trip data."""

    service_type = getattr(estimate, "service_type", "Not provided")
    airport = getattr(estimate, "airport_code", "Not provided")
    location = getattr(estimate, "location_input", "Not provided")
    pickup, dropoff = (airport, location) if service_type == "AIRPORT_PICKUP" else (location, airport)
    lines = [
        "New website booking request",
        f"Customer: {customer_name}",
        f"Preferred Contact: {preferred_contact_method}",
        *tuple(f"{label}: {contact}" for label, contact in (("Phone", phone), ("Email", email), ("WeChat", wechat_id), ("LINE", line_id)) if contact),
        "",
        f"Route: {getattr(estimate, 'route_summary', 'Not provided')}",
        f"Pickup: {pickup}",
        f"Drop-off: {dropoff}",
        f"Airport: {airport}",
        f"Date: {getattr(estimate, 'service_date', 'Not provided')}",
        f"Time: {getattr(estimate, 'service_time', 'Not provided')} {getattr(estimate, 'service_timezone', '')}".rstrip(),
        f"Passengers: {getattr(estimate, 'passenger_count', 'Not provided')}",
        f"Large Luggage: {getattr(estimate, 'large_suitcase_count', 'Not provided')}",
        f"Child Seat: {getattr(estimate, 'child_seat_required', 'Not provided')}",
        f"Oversized Items: {getattr(estimate, 'oversized_items_present', 'Not provided')}",
        f"Source: {source}",
    ]
    flight_number = getattr(estimate, "flight_number", None)
    if flight_number:
        lines.append(f"Flight Number: {flight_number}")
    return "\n".join((*lines, "", _pricing_recommendation_text(estimate)))
