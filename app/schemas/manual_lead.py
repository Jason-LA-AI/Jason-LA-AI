"""Contracts for leads entered from the internal dashboard."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ManualLeadSource(StrEnum):
    FACEBOOK = "FACEBOOK"
    XIAOHONGSHU = "XIAOHONGSHU"
    PHONE = "PHONE"
    WECHAT = "WECHAT"
    OTHER = "OTHER"


class ManualLeadStatus(StrEnum):
    NEW = "NEW"
    QUOTED = "QUOTED"
    WAITING = "WAITING"
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"
    LOST = "LOST"


class ManualLeadIntent(StrEnum):
    AIRPORT_PICKUP = "AIRPORT_PICKUP"
    AIRPORT_DROPOFF = "AIRPORT_DROPOFF"
    PRIVATE_TRANSPORTATION = "PRIVATE_TRANSPORTATION"
    LONG_DISTANCE = "LONG_DISTANCE"


class ManualLeadCreate(BaseModel):
    """Customer and trip details captured by Jason outside the quote form."""

    model_config = ConfigDict(str_strip_whitespace=True)

    customer_name: str = Field(min_length=1, max_length=150)
    source: ManualLeadSource
    status: ManualLeadStatus = ManualLeadStatus.NEW
    phone: str | None = Field(default=None, max_length=30)
    wechat: str | None = Field(default=None, max_length=255)
    social_contact: str | None = Field(default=None, max_length=255)
    intent: ManualLeadIntent | None = None
    service_date: str | None = Field(default=None, max_length=30)
    airport: str | None = Field(default=None, max_length=10)
    pickup: str | None = Field(default=None, max_length=255)
    destination: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def require_contact(self) -> "ManualLeadCreate":
        if not any((self.phone, self.wechat, self.social_contact)):
            raise ValueError("Provide a phone, WeChat, or social contact.")
        return self


class ManualLeadStatusUpdate(BaseModel):
    """Dashboard status change for an existing lead."""

    status: ManualLeadStatus
