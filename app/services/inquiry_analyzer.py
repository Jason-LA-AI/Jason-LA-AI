"""Deterministic inquiry analyzer for Jason AI transportation assistant.

This module extracts customer travel information locally.
It does not call external AI models.
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


ANALYSIS_KNOWLEDGE_FILES = (
    "brand_profile.md",
    "customer_language_rules.md",
    "pricing_rules.md",
    "vehicle_capacity.md",
    "customer_inquiry_flow.md",
    "order_priority_scoring.md",
)


SUPPORTED_AIRPORTS = (
    "LAX",
    "ONT",
    "SNA",
    "BUR",
    "LGB",
)


TRADITIONAL_MARKERS = set(
    "請聯絡機場接機送機羅蘭崗臺灣確認費價車輛"
)


SIMPLIFIED_MARKERS = set(
    "请联系机场接机送机罗兰岗台湾确认费价车辆"
)


CJK_PATTERN = re.compile(
    r"[\u3400-\u9fff]"
)


DATE_PATTERNS = (
    re.compile(r"\d{4}-\d{1,2}-\d{1,2}"),
    re.compile(r"\d{1,2}/\d{1,2}/\d{2,4}"),
    re.compile(r"\d{1,2}月\d{1,2}(?:日|号|號)"),
)


TIME_PATTERNS = (
    re.compile(
        r"(凌晨|早上|上午|中午|下午|晚上)?\s*\d{1,2}点(?:\d{1,2}分)?"
    ),
    re.compile(
        r"\d{1,2}[:：]\d{2}"
    ),
    re.compile(
        r"\d{1,2}\s?(?:am|pm)",
        re.IGNORECASE,
    ),
)


PASSENGER_PATTERN = re.compile(
    r"(?P<count>\d+)\s*(?:passengers?|people|persons?|adults?|adult|travellers?|travelers?|位(?:乘客)?|个人|個人|人)",
    re.IGNORECASE,
)


LUGGAGE_PATTERN = re.compile(
    r"(?P<count>\d+)\s*(?P<label>(?:large\s+)?(?:bags?|suitcases?|luggage)|(?:个|個|件)?(?:大(?:型)?行李|行李|箱子|箱))",
    re.IGNORECASE,
)


FLIGHT_PATTERN = re.compile(
    r"\b[A-Z]{2}\s?\d{1,4}\b",
    re.IGNORECASE,
)



class InquiryAnalyzer:

    def __init__(self) -> None:

        self.business_context = get_combined_business_context(
            ANALYSIS_KNOWLEDGE_FILES
        )


    def analyze(
        self,
        customer_message: str,
        preferred_language: CustomerLanguage | str | None = None,
    ) -> InquiryAnalysis:

        message = customer_message.strip()

        if not message:
            raise ValueError(
                "customer_message must not be empty"
            )


        language = _detect_language(
            message,
            preferred_language,
        )


        inquiry_type = _detect_inquiry_type(
            message
        )


        extracted, luggage_count = _extract_information(
            message,
            inquiry_type,
        )


        missing = _find_missing_information(
            extracted,
            inquiry_type,
        )


        vehicle = _assess_vehicle(
            message,
            extracted.passengers,
            luggage_count,
        )


        risk = _assess_risk(
            missing,
            vehicle,
        )


        action = _recommend_action(
            missing,
            vehicle,
        )


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

    return InquiryAnalyzer().analyze(
        customer_message,
        preferred_language,
    )



def _detect_language(
    message: str,
    preferred_language: CustomerLanguage | str | None,
) -> CustomerLanguage:

    if preferred_language:

        try:
            return CustomerLanguage(
                preferred_language
            )

        except ValueError:
            pass


    if not CJK_PATTERN.search(message):

        return CustomerLanguage.ENGLISH


    traditional = sum(
        c in TRADITIONAL_MARKERS
        for c in message
    )


    simplified = sum(
        c in SIMPLIFIED_MARKERS
        for c in message
    )


    if traditional > simplified:

        return CustomerLanguage.TRADITIONAL_CHINESE


    return CustomerLanguage.SIMPLIFIED_CHINESE
    return CustomerLanguage.SIMPLIFIED_CHINESE



def _detect_inquiry_type(
    message: str,
) -> InquiryType:

    normalized = message.casefold()


    # 机场送机场
    # 例如：
    # ONT机场送到LAX
    # ONT airport to LAX
    if any(
        word in normalized
        for word in (
            "送到lax",
            "送到ont",
            "送到sna",
            "送到bur",
            "送到lgb",
            "机场送到",
            "機場送到",
            "airport to airport",
            "from ont",
            "ont to lax",
        )
    ):
        return InquiryType.AIRPORT_DROPOFF



    # 接机
    if any(
        word in normalized
        for word in (
            "接机",
            "接機",
            "pickup",
            "pick up",
            "airport pickup",
        )
    ):
        return InquiryType.AIRPORT_PICKUP



    # 送机场
    if any(
        word in normalized
        for word in (
            "送机",
            "送機",
            "dropoff",
            "drop-off",
            "送到机场",
            "送到機場",
        )
    ):
        return InquiryType.AIRPORT_DROPOFF



    # 包车
    if any(
        word in normalized
        for word in (
            "包车",
            "包車",
            "private",
            "transportation",
        )
    ):
        return InquiryType.PRIVATE_TRANSPORTATION



    return InquiryType.UNKNOWN




def _extract_information(
    message: str,
    inquiry_type: InquiryType,
) -> tuple[ExtractedInquiryInformation, int | None]:


    date_value = _first_match(
        message,
        DATE_PATTERNS,
    )


    time_value = _first_match(
        message,
        TIME_PATTERNS,
    )


    airport = _extract_airport(
        message
    )


    passenger_match = PASSENGER_PATTERN.search(
        message
    )


    passengers = (

        int(
            passenger_match.group("count")
        )

        if passenger_match

        else None

    )



    luggage_match = LUGGAGE_PATTERN.search(
        message
    )


    luggage_count = (

        int(
            luggage_match.group("count")
        )

        if luggage_match

        else None

    )


    luggage = (

        luggage_match.group(0)

        if luggage_match

        else None

    )



    flight_match = FLIGHT_PATTERN.search(
        message
    )


    flight_information = (

        flight_match.group(0).upper()

        if flight_match

        else None

    )



    pickup_location = None

    destination = None

    pickup_airport = None

    dropoff_airport = None



    if inquiry_type == InquiryType.AIRPORT_PICKUP:

        pickup_airport = airport

        pickup_location = airport

        destination = _extract_known_destination(
            message
        )



    elif inquiry_type == InquiryType.AIRPORT_DROPOFF:


        airports = _extract_airports(
            message
        )


        if len(airports) >= 2:

            pickup_airport = airports[0]

            dropoff_airport = airports[1]

            airport = airports[0]

            destination = airports[1]


        else:

            destination = airport



    return (

        ExtractedInquiryInformation(

            date=date_value,

            pickup_time=time_value,

            airport=airport,

            pickup_airport=pickup_airport,

            dropoff_airport=dropoff_airport,

            pickup_location=pickup_location,

            destination=destination,

            passengers=passengers,

            luggage=luggage,

            flight_information=flight_information,

        ),

        luggage_count,

    )





def _first_match(
    message: str,
    patterns,
):

    for pattern in patterns:

        result = pattern.search(
            message
        )

        if result:

            return result.group(0)


    return None





def _extract_airport(
    message: str,
) -> str | None:


    upper = message.upper()


    for airport in SUPPORTED_AIRPORTS:

        if airport in upper:

            return airport



    names = {
        "安大略机场": "ONT",

        "安大略機場": "ONT",

        "ontario airport": "ONT",

        "ontario机场": "ONT",

        "ontario機場": "ONT",

        "los angeles international airport": "LAX",

        "洛杉矶国际机场": "LAX",

        "洛杉磯國際機場": "LAX",

    }


    normalized = message.casefold()


    for name, code in names.items():

        if name.casefold() in normalized:

            return code


    return None





def _extract_airports(
    message: str,
) -> list[str]:

    upper = message.upper()

    matches = []

    pattern = r"LAX|ONT|SNA|BUR|LGB"

    for match in re.finditer(pattern, upper):

        matches.append(
            match.group(0)
        )

    return matches





def _extract_known_destination(
    message: str,
) -> str | None:


    normalized = message.casefold()


    destinations = {

    "rowland heights":
        "Rowland Heights",

    "罗兰岗":
        "Rowland Heights",

    "羅蘭崗":
        "Rowland Heights",

    "irvine":
        "Irvine",

    "尔湾":
        "Irvine",

    "爾灣":
        "Irvine",

    "chino":
        "Chino",

    "奇诺":
        "Chino",

}


    for name, value in destinations.items():

        if name.casefold() in normalized:

            return value


    return None
def _find_missing_information(
    extracted: ExtractedInquiryInformation,
    inquiry_type: InquiryType,
) -> list[str]:


    missing = []


    if inquiry_type == InquiryType.UNKNOWN:

        missing.append(
            "inquiry_type"
        )


    if extracted.date is None:

        missing.append(
            "date"
        )


    if extracted.pickup_time is None:

        missing.append(
            "pickup_time"
        )


    if (
        extracted.flight_information is None
        and inquiry_type == InquiryType.AIRPORT_PICKUP
    ):

        missing.append(
            "flight_information"
        )


    if inquiry_type in {
        InquiryType.AIRPORT_PICKUP,
        InquiryType.AIRPORT_DROPOFF,
    }:

        if extracted.airport is None:

            missing.append(
                "airport"
            )


    if (
        extracted.destination is None
        and inquiry_type != InquiryType.AIRPORT_DROPOFF
    ):

        missing.append(
            "destination"
        )


    if extracted.passengers is None:

        missing.append(
            "passenger_count"
        )


    if extracted.luggage is None:

        missing.append(
            "luggage_details"
        )


    # 成交前确认项目
    missing.extend(
        [
            "child_seat_requirements",
            "special_requests",
        ]
    )


    return missing





def _assess_vehicle(
    message: str,
    passengers: int | None,
    luggage_count: int | None,
) -> VehicleAssessment:


    if passengers is None and luggage_count is None:

        return VehicleAssessment.INSUFFICIENT_INFORMATION



    if passengers is None or luggage_count is None:

        return VehicleAssessment.NEEDS_CONFIRMATION



    if passengers >= 5 and luggage_count >= 5:

        return VehicleAssessment.NOT_RECOMMENDED



    if passengers == 4 and luggage_count >= 4:

        return VehicleAssessment.NEEDS_CONFIRMATION



    if passengers <= 3 and luggage_count <= 3:

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