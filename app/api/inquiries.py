"""Customer inquiry intake endpoint."""

from datetime import datetime, timezone
import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.session import get_db_session
from app.models.approval import Approval
from app.models.conversation import Conversation
from app.models.customer import Customer
from app.models.lead import Lead
from app.models.order import Order
from app.models.quote import Quote
from app.schemas.inquiry import InquiryCreate, InquiryReceived
from app.schemas.inquiry_analysis import InquiryType, VehicleAssessment
from app.services.inquiry_analyzer import analyze_inquiry
from app.services.pricing_engine import calculate_price
from app.services.reply_generator import generate_initial_reply
from app.services.date_parser import parse_service_datetime
from app.services.telegram_notifier import send_approval_notification
from app.services.order_availability import check_order_availability

router = APIRouter()
logger = logging.getLogger(__name__)


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

    received_at = datetime.now(timezone.utc)

    customer_id = uuid4()
    lead_id = uuid4()
    order_id = uuid4()
    quote_id = uuid4()
    approval_id = uuid4()

    analysis = analyze_inquiry(inquiry.message)

    source = _database_source(
        inquiry.source.value if inquiry.source else None
    )


    customer = Customer(
    id=customer_id,
    display_name=inquiry.customer_name,
    primary_contact=inquiry.customer_phone or f"intake:{customer_id}",
    primary_contact_type=(
        "email"
        if inquiry.customer_phone and "@" in inquiry.customer_phone
        else "phone"
        if inquiry.customer_phone
        else "other"
    ),
    secondary_contact=inquiry.customer_wechat,
    source=source,
    preferred_language=analysis.detected_language.value,
    last_contact_at=received_at,
)


    lead = Lead(
        id=lead_id,
        customer_id=customer_id,
        source=source,
        intent=_database_intent(analysis.inquiry_type),
        status=(
            "AWAITING_DETAILS"
            if analysis.missing_information
            else "PENDING_JASON"
        ),
        received_at=received_at,
        last_contact_at=received_at,
        next_action=analysis.recommended_action.value,
        next_action_owner=(
            "CUSTOMER"
            if analysis.missing_information
            else "JASON"
        ),
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

    service_datetime = parse_service_datetime(
        analysis.extracted_information.date,
        analysis.extracted_information.pickup_time,
    )
    available = True

    if service_datetime:

        available = check_order_availability(
            db_session,
            service_datetime,
        )

    order = Order(
        id=order_id,
        customer_id=customer_id,
        lead_id=lead_id,

        pickup_at=service_datetime,

        service_date=(
        service_datetime.date()
        if service_datetime
        else None
    ),

    status=(
        "WAITING_FOR_INFORMATION"
        if analysis.missing_information
        else "WAITING_FOR_JASON_APPROVAL"
    ),

    intent=(
        _database_intent(analysis.inquiry_type)
        or "PRIVATE_TRANSPORTATION"
    ),

    vehicle_assessment=_database_vehicle_assessment(
        analysis.vehicle_assessment
    ),

    risk_level=analysis.risk_level.value,
    missing_information=analysis.missing_information,
    next_action=analysis.recommended_action.value,
    next_action_owner=(
        "CUSTOMER"
        if analysis.missing_information
        else "JASON"
    ),
)

    service_datetime = parse_service_datetime(
        analysis.extracted_information.date,
        analysis.extracted_information.pickup_time,
)

    pricing_result = None

    if not analysis.missing_information:
        pricing_result = calculate_price(
            analysis.extracted_information.airport,
            analysis.extracted_information.destination,
            None,
        )


    quote = Quote(
        id=quote_id,
        order_id=order_id,
        version_number=1,
        status="DRAFT",
        currency_code="USD",
        quote_type="ONE_WAY",
        knowledge_version="v1",

        suggested_amount=(
            pricing_result.suggested_amount
            if pricing_result
            else None
        ),

        suggested_min_amount=(
            pricing_result.minimum_amount
            if pricing_result
            else None
        ),

        suggested_max_amount=(
            pricing_result.maximum_amount
            if pricing_result
            else None
        ),

        pricing_source=(
            pricing_result.pricing_source
            if pricing_result
            else None
        ),

        additional_fee_factors=(
            pricing_result.factors
            if pricing_result
            else None
        ),
    )
    approval = Approval(
        id=approval_id,
        order_id=order_id,
        quote_id=quote_id,
        approval_type="FINAL_PRICE",
        status="PENDING",
        requested_by="AI",
        requested_at=received_at,
        request_summary="Jason approval required for customer inquiry.",
        proposed_value={
            "quote_id": str(quote_id),
            "lead_id": str(lead_id),
        },
    )


    conversation = Conversation(
        id=uuid4(),
        customer_id=customer_id,
        lead_id=lead_id,
        order_id=order_id,
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


    reply = generate_initial_reply(
        inquiry.customer_name,
        analysis.extracted_information,
        analysis.missing_information,
)


    reply_conversation = Conversation(
        id=uuid4(),
        customer_id=customer_id,
        lead_id=lead_id,
        order_id=order_id,
        channel=_conversation_channel(source),
        direction="OUTBOUND",
        sender_type="JASON",
        language_code=analysis.detected_language.value,
        message_text=reply,
        customer_visible=True,
        ai_generated=True,
        approval_required=False,
        delivery_status="DRAFT",
    )


    try:
        db_session.add_all(
            (
                customer,
                lead,
                order,
                quote,
                approval,
                conversation,
                reply_conversation,
            )
        )

        db_session.commit()
    except Exception:
        db_session.rollback()
        raise

    try:
        send_approval_notification(
    str(approval_id),
    f"""
🚗 新接送询价

客户:
{inquiry.customer_name or "网站客户"}

联系方式:
{inquiry.customer_phone or "未提供"}

微信:
{inquiry.customer_wechat or "未提供"}

日期:
{analysis.extracted_information.date or "未提供"}

时间:
{analysis.extracted_information.pickup_time or "未提供"}

接送地点:
{
    analysis.extracted_information.airport
    or analysis.extracted_information.pickup_location
    or "未提供"
}

目的地:
{analysis.extracted_information.destination or "未提供"}

人数:
{analysis.extracted_information.passengers or "未提供"}

行李:
{analysis.extracted_information.luggage or "未提供"}

航班:
{analysis.extracted_information.flight_information or "未提供"}

AI建议价格:
{
    pricing_result.suggested_amount
    if pricing_result
    else "需要人工审核"
}
档期:
{"🟢 可以安排" if available else "🔴 时间冲突"}

请审核。
"""
        )
    except Exception as exc:
        # The inquiry is already persisted. Notification delivery must not turn
        # a successful customer submission into an HTTP 500 response. Avoid
        # logging the exception message because requests may include the bot
        # token in its URL.
        logger.error(
            "Telegram notification failed after inquiry persisted (%s)",
            type(exc).__name__,
        )


    return {
        "inquiry_id": lead_id,
        "received_at": received_at,
        "reply": reply,
    }



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



def _database_intent(
    inquiry_type: InquiryType,
) -> str | None:
    return {
        InquiryType.AIRPORT_PICKUP: "AIRPORT_PICKUP",
        InquiryType.AIRPORT_DROPOFF: "AIRPORT_DROPOFF",
        InquiryType.PRIVATE_TRANSPORTATION: "PRIVATE_TRANSPORTATION",
    }.get(inquiry_type)



def _database_vehicle_assessment(
    assessment: VehicleAssessment,
) -> str:
    return {
        VehicleAssessment.LIKELY_COMFORTABLE:
            "LIKELY_COMFORTABLE",

        VehicleAssessment.NEEDS_CONFIRMATION:
            "NEEDS_CONFIRMATION",

        VehicleAssessment.NOT_RECOMMENDED:
            "NOT_RECOMMENDED",

        VehicleAssessment.INSUFFICIENT_INFORMATION:
            "INSUFFICIENT_INFORMATION",
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
