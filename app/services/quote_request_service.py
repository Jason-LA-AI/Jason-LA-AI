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
        phone = request.phone.strip() if request.phone else None
        email = str(request.email) if request.email else None

        if not phone and not email:
            raise QuoteRequestError(CONTACT_METHOD_REQUIRED)
        if (
            request.preferred_contact_method == PreferredContactMethod.SMS
            and not phone
        ):
            raise QuoteRequestError(PHONE_REQUIRED_FOR_SMS)
        if (
            request.preferred_contact_method == PreferredContactMethod.EMAIL
            and not email
        ):
            raise QuoteRequestError(EMAIL_REQUIRED_FOR_EMAIL)

        customer = create_or_match_customer(
            db,
            customer_name=request.customer_name,
            phone=phone,
            email=email,
            preferred_contact_method=request.preferred_contact_method,
            source=request.source.value,
        )
        lead = create_lead_from_quote_request(
            db,
            customer=customer,
            quote_estimate=estimate,
            customer_contact_information={
                "phone": phone,
                "email": email,
                "preferred_contact_method": request.preferred_contact_method.value,
            },
            source=request.source.value,
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
            source=request.source.value,
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
                "New website booking request\n"
                f"Customer: {customer.display_name}\n"
                f"Route: {estimate.route_summary}\n"
                f"Service: {estimate.service_type}\n"
                f"Source: {request.source.value}\n"
                f"Phone: {phone or '-'}\nEmail: {email or '-'}\n\n"
                + _pricing_recommendation_text(estimate),
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


def _pricing_recommendation_text(estimate: object) -> str:
    source = getattr(estimate, "pricing_source", None) or "Not provided"
    status_value = getattr(estimate, "status", None) or "MANUAL_REVIEW_REQUIRED"
    suggested = getattr(estimate, "suggested_amount", None)
    minimum = getattr(estimate, "estimated_min_amount", None)
    maximum = getattr(estimate, "estimated_max_amount", None)
    if suggested is None or minimum is None or maximum is None:
        return (
            "Pricing Recommendation:\n"
            "Manual Review Required\n"
            f"Pricing Source: {source}\n"
            f"Pricing Status: {status_value}"
        )
    currency = getattr(estimate, "currency_code", None) or "USD"
    return (
        "Pricing Recommendation:\n"
        f"Suggested Amount: {suggested}\n"
        f"Range: {minimum} - {maximum}\n"
        f"Currency: {currency}\n"
        f"Pricing Source: {source}\n"
        f"Pricing Status: {status_value}"
    )
