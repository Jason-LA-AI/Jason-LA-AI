"""Structured schemas returned by the placeholder inquiry analyzer."""

from enum import StrEnum

from pydantic import BaseModel


class CustomerLanguage(StrEnum):
    ENGLISH = "English"
    SIMPLIFIED_CHINESE = "zh-CN"
    TRADITIONAL_CHINESE = "zh-TW"


class InquiryType(StrEnum):
    AIRPORT_PICKUP = "airport pickup"
    AIRPORT_DROPOFF = "airport dropoff"
    PRIVATE_TRANSPORTATION = "private transportation"
    UNKNOWN = "unknown"


class VehicleAssessment(StrEnum):
    LIKELY_COMFORTABLE = "likely comfortable"
    NEEDS_CONFIRMATION = "needs confirmation"
    NOT_RECOMMENDED = "not recommended"
    INSUFFICIENT_INFORMATION = "insufficient information"


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RecommendedAction(StrEnum):
    REQUEST_MORE_INFORMATION = "request more information"
    REQUEST_JASON_REVIEW = "request Jason review"
    RECOMMEND_DECLINE = "recommend decline"


class ExtractedInquiryInformation(BaseModel):
    """Facts conservatively extracted from the customer message."""

    date: str | None = None
    airport: str | None = None
    pickup_location: str | None = None
    destination: str | None = None
    passengers: int | None = None
    luggage: str | None = None
    flight_information: str | None = None


class InquiryAnalysis(BaseModel):
    """Structured result of an inquiry analysis pass."""

    detected_language: CustomerLanguage
    inquiry_type: InquiryType
    extracted_information: ExtractedInquiryInformation
    missing_information: list[str]
    vehicle_assessment: VehicleAssessment
    risk_level: RiskLevel
    recommended_action: RecommendedAction
