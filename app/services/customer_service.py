"""Customer matching and creation for the V2.1 quote flow."""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.customer import Customer


_PHONE_ALLOWED_PATTERN = re.compile(r"^\+?[0-9\s().-]+$")


def create_or_match_customer(
    db: Session,
    *,
    customer_name: str,
    phone: str | None,
    email: str | None,
    wechat_id: str | None,
    line_id: str | None,
    preferred_contact_method: str,
    source: str,
) -> Customer:
    """Return an exactly contact-matched customer or create a new profile.

    No shared identifier means no automatic merge: display names are never used
    for matching, because names are neither unique nor reliable identifiers.
    """

    phone_number = phone.strip() if phone else None
    email_address = email.strip() if email else None
    wechat_handle = wechat_id.strip() if wechat_id else None
    line_handle = line_id.strip() if line_id else None
    phone_normalized = _normalize_phone(phone_number)
    email_normalized = email_address.lower() if email_address else None

    if phone_normalized:
        customer = db.scalar(
            select(Customer).where(
                Customer.phone_number_normalized == phone_normalized
            )
        )
        if customer is not None:
            return customer

    if email_normalized:
        customer = db.scalar(
            select(Customer).where(Customer.email_normalized == email_normalized)
        )
        if customer is not None:
            return customer

    if wechat_handle:
        customer = db.scalar(
            select(Customer).where(
                Customer.primary_contact_type == "wechat",
                Customer.primary_contact == wechat_handle,
            )
        )
        if customer is not None:
            return customer

    if line_handle:
        customer = db.scalar(
            select(Customer).where(
                Customer.preferred_contact_method == "LINE",
                Customer.primary_contact == line_handle,
            )
        )
        if customer is not None:
            return customer

    contact_method = (
        preferred_contact_method.value
        if hasattr(preferred_contact_method, "value")
        else preferred_contact_method
    )
    if contact_method == "SMS":
        primary_contact = phone_normalized
        primary_contact_type = "phone"
    elif contact_method == "EMAIL":
        primary_contact = email_normalized
        primary_contact_type = "email"
    elif contact_method == "WECHAT":
        primary_contact = wechat_handle
        primary_contact_type = "wechat"
    else:
        primary_contact = line_handle
        # The existing database constraint has no dedicated LINE value. Keep the
        # channel in preferred_contact_method and use the existing safe fallback.
        primary_contact_type = "other"

    customer = Customer(
        display_name=customer_name.strip(),
        primary_contact=primary_contact,
        primary_contact_type=primary_contact_type,
        source=source,
        preferred_contact_method=contact_method,
        phone_number=phone_number,
        phone_number_normalized=phone_normalized,
        email=email_address,
        email_normalized=email_normalized,
    )
    db.add(customer)
    db.flush()
    return customer


def _normalize_phone(phone: str | None) -> str | None:
    """Normalize safe formatting without inferring a country calling code."""

    if not phone:
        return None
    if not _PHONE_ALLOWED_PATTERN.fullmatch(phone):
        return phone

    digits = "".join(character for character in phone if character.isdigit())
    if not 7 <= len(digits) <= 15:
        return phone
    return f"+{digits}" if phone.startswith("+") else digits
