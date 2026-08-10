"""Idempotent development seed data for the inquiry workflow."""

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.customer import Customer
from app.models.lead import Lead
from app.schemas.inquiry_analysis import InquiryType, VehicleAssessment
from app.services.inquiry_analyzer import analyze_inquiry


SEED_CONTACT_PREFIX = "development-seed:"


@dataclass(frozen=True)
class DevelopmentInquiry:
    key: str
    customer_name: str
    source: str
    message: str
    expected_language: str
    expected_risk: str
    expected_vehicle_assessment: str
    expected_action: str


DEVELOPMENT_INQUIRIES: tuple[DevelopmentInquiry, ...] = (
    DevelopmentInquiry(
        key="taiwan-ont-rowland-heights",
        customer_name="Development Taiwan Customer",
        source="XIAOHONGSHU",
        message=(
            "您好，我是台灣旅客，想預約 ONT 接機，2位乘客、4個大行李，"
            "送到羅蘭崗 Rowland Heights。"
        ),
        expected_language="zh-TW",
        expected_risk="MEDIUM",
        expected_vehicle_assessment="needs confirmation",
        expected_action="request more information",
    ),
    DevelopmentInquiry(
        key="english-ontario-airport",
        customer_name="Development English Customer",
        source="WEBSITE",
        message="Hello, I need transportation from Ontario Airport. Can you provide a quote?",
        expected_language="English",
        expected_risk="MEDIUM",
        expected_vehicle_assessment="insufficient information",
        expected_action="request more information",
    ),
    DevelopmentInquiry(
        key="high-risk-lax-capacity",
        customer_name="Development Capacity Risk Customer",
        source="FACEBOOK",
        message="I need a late-night LAX airport pickup for 5 adults with 6 large suitcases.",
        expected_language="English",
        expected_risk="HIGH",
        expected_vehicle_assessment="not recommended",
        expected_action="recommend decline",
    ),
)


def seed_development_inquiries(db_session: Session) -> int:
    """Insert missing development inquiries and return the inserted count."""
    inserted = 0
    now = datetime.now(timezone.utc)

    for seed in DEVELOPMENT_INQUIRIES:
        contact = f"{SEED_CONTACT_PREFIX}{seed.key}"
        existing_id = db_session.scalar(
            select(Customer.id).where(Customer.primary_contact == contact)
        )
        if existing_id is not None:
            continue

        analysis = analyze_inquiry(seed.message)
        _validate_expected_analysis(seed, analysis.model_dump(mode="json"))
        customer_id = uuid4()
        lead_id = uuid4()

        customer = Customer(
            id=customer_id,
            display_name=seed.customer_name,
            primary_contact=contact,
            primary_contact_type="other",
            source=seed.source,
            source_detail="LOCAL_DEVELOPMENT_SEED",
            preferred_language=analysis.detected_language.value,
            last_contact_at=now,
        )
        lead = Lead(
            id=lead_id,
            customer_id=customer_id,
            source=seed.source,
            intent=_database_intent(analysis.inquiry_type),
            status="AWAITING_DETAILS" if analysis.missing_information else "PENDING_JASON",
            received_at=now,
            last_contact_at=now,
            next_action=analysis.recommended_action.value,
            next_action_owner="CUSTOMER" if analysis.missing_information else "JASON",
            missing_information=analysis.missing_information,
            analysis_result=analysis.model_dump(mode="json"),
            customer_message_summary=seed.message,
            vehicle_assessment=_database_vehicle_assessment(analysis.vehicle_assessment),
            risk_level=analysis.risk_level.value,
            priority_override=(
                "AVOID_RECOMMENDED"
                if analysis.vehicle_assessment == VehicleAssessment.NOT_RECOMMENDED
                else "INFORMATION_REQUIRED"
                if analysis.missing_information
                else "JASON_REVIEW_REQUIRED"
            ),
            jason_decision_needed=analysis.recommended_action.value,
            knowledge_version="development-seed-v1",
        )
        conversation = Conversation(
            id=uuid4(),
            customer_id=customer_id,
            lead_id=lead_id,
            channel=_conversation_channel(seed.source),
            direction="INBOUND",
            sender_type="CUSTOMER",
            language_code=analysis.detected_language.value,
            message_text=seed.message,
            customer_visible=True,
            ai_generated=False,
            approval_required=False,
            delivery_status="NOT_APPLICABLE",
        )
        db_session.add_all((customer, lead, conversation))
        inserted += 1

    try:
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise
    return inserted


def _validate_expected_analysis(seed: DevelopmentInquiry, result: dict[str, object]) -> None:
    expected = {
        "detected_language": seed.expected_language,
        "risk_level": seed.expected_risk,
        "vehicle_assessment": seed.expected_vehicle_assessment,
        "recommended_action": seed.expected_action,
    }
    actual = {key: result.get(key) for key in expected}
    if actual != expected:
        raise RuntimeError(
            f"Development seed analysis changed for {seed.key}: "
            f"expected {expected}, received {actual}"
        )


def _database_intent(inquiry_type: InquiryType) -> str | None:
    return {
        InquiryType.AIRPORT_PICKUP: "AIRPORT_PICKUP",
        InquiryType.AIRPORT_DROPOFF: "AIRPORT_DROPOFF",
        InquiryType.PRIVATE_TRANSPORTATION: "PRIVATE_TRANSPORTATION",
    }.get(inquiry_type)


def _database_vehicle_assessment(assessment: VehicleAssessment) -> str:
    return {
        VehicleAssessment.LIKELY_COMFORTABLE: "LIKELY_COMFORTABLE",
        VehicleAssessment.NEEDS_CONFIRMATION: "NEEDS_CONFIRMATION",
        VehicleAssessment.NOT_RECOMMENDED: "NOT_RECOMMENDED",
        VehicleAssessment.INSUFFICIENT_INFORMATION: "INSUFFICIENT_INFORMATION",
    }[assessment]


def _conversation_channel(source: str) -> str:
    return {
        "XIAOHONGSHU": "XIAOHONGSHU",
        "FACEBOOK": "FACEBOOK",
        "GOOGLE_WEBSITE": "GOOGLE_WEBSITE",
    }.get(source, "MANUAL")
