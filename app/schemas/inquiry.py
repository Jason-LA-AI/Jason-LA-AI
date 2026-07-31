"""Pydantic schemas for customer inquiry intake."""

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InquirySource(StrEnum):
    """Customer sources supported by the initial intake endpoint."""

    XIAOHONGSHU = "Xiaohongshu"
    FACEBOOK = "Facebook"
    WEBSITE = "Website"
    REFERRAL = "Referral"


class InquiryCreate(BaseModel):
    """Customer inquiry intake payload."""

    model_config = ConfigDict(str_strip_whitespace=True)

    message: str = Field(min_length=1, description="Customer's original message")

    customer_name: str | None = Field(
        default=None,
        description="Customer name when provided",
    )

    customer_phone: str | None = Field(
        default=None,
        description="Customer phone or email when provided",
    )

    customer_wechat: str | None = Field(
        default=None,
        description="Customer WeChat when provided",
    )

    source: InquirySource | None = Field(
        default=None,
        description="Channel or source of the inquiry",
    )


class InquiryReceived(BaseModel):
    """Acknowledgement returned after accepting an inquiry."""

    status: Literal["inquiry received"] = "inquiry received"
    inquiry_id: UUID
    received_at: datetime
    reply: str