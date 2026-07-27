"""Customer inquiry intake endpoint."""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.session import get_db_session
from app.models.conversation import Conversation
from app.models.customer import Customer
from app.models.lead import Lead
from app.schemas.inquiry import InquiryCreate, InquiryReceived
from app.schemas.inquiry_analysis import InquiryType, VehicleAssessment
from app.services.inquiry_analyzer import analyze_inquiry


router = APIRouter()


@router.post(
    "",
    response_model=InquiryReceived,
    status_code=status.HTTP_201_CREATED,
    summary="Receive a customer inquiry",
)
def create_inquiry(
    inquiry: InquiryCreate,
    db_session: Session = Depends(get_db_session),
) -> InquiryReceived:
    """Analyze and persist a new customer inquiry in one transaction."""
    received_at = datetime.now(timezone.utc)
    customer_id = uuid4()
    lead_id = uuid4()
    analysis = analyze_inquiry(inquiry.message)
    source = _database_source(inquiry.source.value if inquiry.source else None)

    customer = Customer(
        id=customer_id,
        display_name=inquiry.customer_name,
        # The initial API has no contact field. This internal identifier avoids
        # inventing customer contact data and can be replaced after follow-up.
        primary_contact=f"intake:{customer_id}",
        primary_contact_type="other",
        source=source,
        preferred_language=analysis.detected_language.value,
        last_contact_at=received_at,
    )
    lead = Lead(
        id=lead_id,
        customer_id=customer_id,
        source=source,
        intent=_database_intent(analysis.inquiry_type),
        status=("AWAITING_DETAILS" if analysis.missing_information else "PENDING_JASON"),
        received_at=received_at,
        last_contact_at=received_at,
        next_action=analysis.recommended_action.value,
        next_action_owner=("CUSTOMER" if analysis.missing_information else "JASON"),
        missing_information=analysis.missing_information,
        analysis_result=analysis.model_dump(mode="json"),
        vehicle_assessment=_database_vehicle_assessment(
            analysis.vehicle_assessment
        ),
        risk_level=analysis.risk_level.value,
        priority_override=_priority_override(
            analysis.vehicle_assessment,
            analysis.missing_information,
        ),
        jason_decision_needed=analysis.recommended_action.value,
    )
    conversation = Conversation(
        id=uuid4(),
        customer_id=customer_id,
        lead_id=lead_id,
        channel=_conversation_channel(source),
        direction="INBOUND",
        sender_type="CUSTOMER",
        language_code=analysis.detected_language.value,
        message_text=inquiry.message,
        customer_visible=True,
        ai_generated=False,
        approval_required=False,
        delivery_status="NOT_APPLICABLE",
    )

    try:
        db_session.add_all((customer, lead, conversation))
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise

    return InquiryReceived(inquiry_id=lead_id, received_at=received_at)


def _database_source(source: str | None) -> str:
    return {
        "Xiaohongshu": "XIAOHONGSHU",
        "Facebook": "FACEBOOK",
        "Website": "GOOGLE_WEBSITE",
        "Referral": "REFERRAL",
    }.get(source, "UNKNOWN")


def _conversation_channel(source: str) -> str:
    return {
        "XIAOHONGSHU": "XIAOHONGSHU",
        "FACEBOOK": "FACEBOOK",
        "GOOGLE_WEBSITE": "GOOGLE_WEBSITE",
    }.get(source, "MANUAL")


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


def _priority_override(
    assessment: VehicleAssessment,
    missing_information: list[str],
) -> str:
    if assessment == VehicleAssessment.NOT_RECOMMENDED:
        return "AVOID_RECOMMENDED"
    if missing_information:
        return "INFORMATION_REQUIRED"
    return "JASON_REVIEW_REQUIRED"
