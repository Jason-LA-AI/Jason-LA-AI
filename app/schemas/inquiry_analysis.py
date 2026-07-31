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
    """
    Facts conservatively extracted from the customer message.

    Supports:
    - Airport pickup:
        LAX -> Rowland Heights

    - Airport transfer:
        ONT -> LAX
    """

    # 用车日期
    date: str | None = None

    # 时间
    pickup_time: str | None = None


    # 单机场兼容字段
    # 旧代码继续使用
    airport: str | None = None


    # 新增：机场接送方向
    # 例如：
    # ONT机场送到LAX
    # pickup_airport = ONT
    # dropoff_airport = LAX

    pickup_airport: str | None = None

    dropoff_airport: str | None = None


    # 普通上车地点
    pickup_location: str | None = None


    # 目的地
    destination: str | None = None


    # 客户信息
    passengers: int | None = None

    luggage: str | None = None


    # 航班
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