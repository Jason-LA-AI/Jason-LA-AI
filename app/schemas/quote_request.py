"""Pydantic contracts for accepting an estimate and requesting review."""

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class PreferredContactMethod(StrEnum):
    """Customer contact channels supported by V2.1."""

    SMS = "SMS"
    EMAIL = "EMAIL"


class QuoteRequestCreate(BaseModel):
    """Customer acceptance and contact details for a formal quote request."""

    model_config = ConfigDict(str_strip_whitespace=True)

    estimate_id: UUID
    customer_name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    preferred_contact_method: PreferredContactMethod
    estimate_acceptance: Literal[True]


class QuoteRequestReceived(BaseModel):
    """Acknowledgement returned after validating an accepted estimate."""

    status: Literal["ESTIMATE_ACCEPTED"] = "ESTIMATE_ACCEPTED"
    estimate_id: UUID
    message: str = "Estimate accepted. Your request is ready for Jason review."
