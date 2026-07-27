"""Deterministic placeholder analysis for customer inquiry messages.

This module intentionally performs only conservative, local extraction. It
loads the approved business knowledge context but does not call an AI model,
persist data, quote prices, or confirm bookings.
"""

from __future__ import annotations

import re

from app.schemas.inquiry_analysis import (
    CustomerLanguage,
    ExtractedInquiryInformation,
    InquiryAnalysis,
    InquiryType,
    RecommendedAction,
    RiskLevel,
    VehicleAssessment,
)
from app.services.knowledge_loader import get_combined_business_context


ANALYSIS_KNOWLEDGE_FILES: tuple[str, ...] = (
    "brand_profile.md",
    "customer_language_rules.md",
    "pricing_rules.md",
    "vehicle_capacity.md",
    "customer_inquiry_flow.md",
    "order_priority_scoring.md",
)

SUPPORTED_AIRPORTS: tuple[str, ...] = ("LAX", "ONT", "SNA", "BUR", "LGB")
TRADITIONAL_MARKERS = set("請聯絡機場接機送機羅蘭崗臺灣確認費價車輛與為這還會號碼時間")
SIMPLIFIED_MARKERS = set("请联系机场接机送机罗兰岗台湾确认费价车辆与为这还会号码时间")
CJK_PATTERN = re.compile(r"[\u3400-\u9fff]")

DATE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b\d{4}-\d{1,2}-\d{1,2}\b"),
    re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),
    re.compile(r"\d{1,2}月\d{1,2}(?:日|号|號)"),
)
PASSENGER_PATTERN = re.compile(
    r"(?P<count>\d+)\s*(?:passengers?|people|persons?|adults?|位(?:乘客)?|个人|個人|人)",
    re.IGNORECASE,
)
LUGGAGE_PATTERN = re.compile(
    r"(?P<count>\d+)\s*(?P<label>(?:large\s+)?(?:bags?|suitcases?)|"
    r"(?:个|個|件)?(?:大(?:型)?行李|行李|箱子|箱))",
    re.IGNORECASE,
)
FLIGHT_PATTERN = re.compile(r"\b[A-Z]{2}\s?\d{1,4}\b", re.IGNORECASE)


class InquiryAnalyzer:
    """Knowledge-backed interface with conservative placeholder logic."""

    def __init__(self) -> None:
        self.business_context = get_combined_business_context(
            ANALYSIS_KNOWLEDGE_FILES
        )

    def analyze(
        self,
        customer_message: str,
        preferred_language: CustomerLanguage | str | None = None,
    ) -> InquiryAnalysis:
        """Analyze one customer message without AI or persistence."""
        message = customer_message.strip()
        if not message:
            raise ValueError("customer_message must not be empty")

        language = _detect_language(message, preferred_language)
        inquiry_type = _detect_inquiry_type(message)
        extracted, luggage_count = _extract_information(message, inquiry_type)
        missing = _find_missing_information(extracted, inquiry_type)
        vehicle = _assess_vehicle(message, extracted.passengers, luggage_count)
        risk = _assess_risk(missing, vehicle)
        action = _recommend_action(missing, vehicle)

        return InquiryAnalysis(
            detected_language=language,
            inquiry_type=inquiry_type,
            extracted_information=extracted,
            missing_information=missing,
            vehicle_assessment=vehicle,
            risk_level=risk,
            recommended_action=action,
        )


def analyze_inquiry(
    customer_message: str,
    preferred_language: CustomerLanguage | str | None = None,
) -> InquiryAnalysis:
    """Convenience interface for a single placeholder analysis."""
    return InquiryAnalyzer().analyze(customer_message, preferred_language)


def _detect_language(
    message: str,
    preferred_language: CustomerLanguage | str | None,
) -> CustomerLanguage:
    normalized_preference: CustomerLanguage | None = None
    if preferred_language is not None:
        try:
            normalized_preference = CustomerLanguage(preferred_language)
        except ValueError as error:
            raise ValueError(
                "preferred_language must be English, zh-CN, or zh-TW"
            ) from error

    has_cjk = bool(CJK_PATTERN.search(message))
    if not has_cjk:
        return CustomerLanguage.ENGLISH

    traditional_score = sum(character in TRADITIONAL_MARKERS for character in message)
    simplified_score = sum(character in SIMPLIFIED_MARKERS for character in message)
    if traditional_score > simplified_score:
        return CustomerLanguage.TRADITIONAL_CHINESE
    if simplified_score > traditional_score:
        return CustomerLanguage.SIMPLIFIED_CHINESE
    if normalized_preference in {
        CustomerLanguage.SIMPLIFIED_CHINESE,
        CustomerLanguage.TRADITIONAL_CHINESE,
    }:
        return normalized_preference

    # Shared Chinese characters can be ambiguous in short messages. The
    # placeholder uses zh-CN provisionally; a future AI analyzer should expose
    # confidence and ask for preference when the distinction matters.
    return CustomerLanguage.SIMPLIFIED_CHINESE


def _detect_inquiry_type(message: str) -> InquiryType:
    normalized = message.casefold()
    has_airport = _extract_airport(message) is not None
    if any(term in normalized for term in ("接机", "接機", "airport pickup")) or (
        has_airport and "pickup" in normalized
    ) or (
        has_airport and re.search(r"\bfrom\s+(?:the\s+)?(?:ontario\s+)?airport\b", normalized)
    ):
        return InquiryType.AIRPORT_PICKUP
    if any(
        term in normalized
        for term in ("送机", "送機", "airport dropoff", "airport drop-off")
    ) or (has_airport and any(term in normalized for term in ("dropoff", "drop-off"))):
        return InquiryType.AIRPORT_DROPOFF
    if any(
        term in normalized
        for term in (
            "private transportation",
            "private transport",
            "私人用车",
            "私人用車",
            "包车",
            "包車",
            "long distance",
            "长途",
            "長途",
        )
    ):
        return InquiryType.PRIVATE_TRANSPORTATION
    return InquiryType.UNKNOWN


def _extract_information(
    message: str,
    inquiry_type: InquiryType,
) -> tuple[ExtractedInquiryInformation, int | None]:
    date_value = _first_match(message, DATE_PATTERNS)
    airport = _extract_airport(message)
    passenger_match = PASSENGER_PATTERN.search(message)
    passengers = (
        int(passenger_match.group("count")) if passenger_match is not None else None
    )
    luggage_match = LUGGAGE_PATTERN.search(message)
    luggage_count = (
        int(luggage_match.group("count")) if luggage_match is not None else None
    )
    luggage = luggage_match.group(0) if luggage_match is not None else None
    flight_match = FLIGHT_PATTERN.search(message)
    flight_information = flight_match.group(0).upper() if flight_match else None

    pickup_location = airport if inquiry_type == InquiryType.AIRPORT_PICKUP else None
    destination = airport if inquiry_type == InquiryType.AIRPORT_DROPOFF else None
    if inquiry_type == InquiryType.AIRPORT_PICKUP:
        destination = _extract_known_destination(message)

    return (
        ExtractedInquiryInformation(
            date=date_value,
            airport=airport,
            pickup_location=pickup_location,
            destination=destination,
            passengers=passengers,
            luggage=luggage,
            flight_information=flight_information,
        ),
        luggage_count,
    )


def _first_match(message: str, patterns: tuple[re.Pattern[str], ...]) -> str | None:
    for pattern in patterns:
        match = pattern.search(message)
        if match is not None:
            return match.group(0)
    return None


def _extract_airport(message: str) -> str | None:
    upper_message = message.upper()
    for airport in SUPPORTED_AIRPORTS:
        if re.search(rf"(?<![A-Z0-9]){airport}(?![A-Z0-9])", upper_message):
            return airport

    normalized = message.casefold()
    airport_names = {
        "ontario airport": "ONT",
        "ontario机场": "ONT",
        "ontario機場": "ONT",
        "los angeles international airport": "LAX",
        "洛杉矶国际机场": "LAX",
        "洛杉磯國際機場": "LAX",
    }
    for name, code in airport_names.items():
        if name.casefold() in normalized:
            return code
    return None


def _extract_known_destination(message: str) -> str | None:
    """Extract only explicitly supported, unambiguous destination names."""
    normalized = message.casefold()
    if any(
        name in normalized
        for name in ("rowland heights", "罗兰岗", "羅蘭崗")
    ):
        return "Rowland Heights"
    return None


def _find_missing_information(
    extracted: ExtractedInquiryInformation,
    inquiry_type: InquiryType,
) -> list[str]:
    missing: list[str] = []
    if inquiry_type == InquiryType.UNKNOWN:
        missing.append("inquiry_type")
    if extracted.date is None:
        missing.append("date")
    missing.append("pickup_time")
    if extracted.airport is None and inquiry_type in {
        InquiryType.AIRPORT_PICKUP,
        InquiryType.AIRPORT_DROPOFF,
    }:
        missing.append("airport")
    if extracted.flight_information is None and inquiry_type in {
        InquiryType.AIRPORT_PICKUP,
        InquiryType.AIRPORT_DROPOFF,
    }:
        missing.append("flight_information")
    if extracted.pickup_location is None:
        missing.append("pickup_location")
    if extracted.destination is None:
        missing.append("destination")
    if extracted.passengers is None:
        missing.append("passenger_count")
    if extracted.luggage is None:
        missing.append("luggage_details")
    missing.extend(("child_seat_requirements", "special_requests"))
    return missing


def _assess_vehicle(
    message: str,
    passengers: int | None,
    luggage_count: int | None,
) -> VehicleAssessment:
    if passengers is None or luggage_count is None:
        return VehicleAssessment.INSUFFICIENT_INFORMATION
    if passengers >= 5 and luggage_count >= 5:
        return VehicleAssessment.NOT_RECOMMENDED
    if passengers == 4 and luggage_count >= 4:
        return VehicleAssessment.NEEDS_CONFIRMATION

    normalized = message.casefold()
    normal_luggage_stated = any(
        term in normalized
        for term in ("normal luggage", "一般行李", "正常行李")
    )
    if 1 <= passengers <= 3 and normal_luggage_stated:
        return VehicleAssessment.LIKELY_COMFORTABLE
    return VehicleAssessment.NEEDS_CONFIRMATION


def _assess_risk(
    missing: list[str],
    vehicle: VehicleAssessment,
) -> RiskLevel:
    if vehicle == VehicleAssessment.NOT_RECOMMENDED:
        return RiskLevel.HIGH
    if missing or vehicle in {
        VehicleAssessment.NEEDS_CONFIRMATION,
        VehicleAssessment.INSUFFICIENT_INFORMATION,
    }:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _recommend_action(
    missing: list[str],
    vehicle: VehicleAssessment,
) -> RecommendedAction:
    if vehicle == VehicleAssessment.NOT_RECOMMENDED:
        return RecommendedAction.RECOMMEND_DECLINE
    if missing:
        return RecommendedAction.REQUEST_MORE_INFORMATION
    return RecommendedAction.REQUEST_JASON_REVIEW
