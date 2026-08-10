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
    preferred_contact_method: str,
    source: str,
) -> Customer:
    """Return a contact-matched customer or create a new customer profile."""

    phone_number = phone.strip() if phone else None
    email_address = email.strip() if email else None
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

    contact_method = (
        preferred_contact_method.value
        if hasattr(preferred_contact_method, "value")
        else preferred_contact_method
    )
    if contact_method == "SMS":
        primary_contact = phone_normalized
        primary_contact_type = "phone"
    else:
        primary_contact = email_normalized
        primary_contact_type = "email"

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
