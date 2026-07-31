"""AI chat inquiry endpoint."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.conversation import Conversation

from app.database.session import get_db_session
from app.schemas.inquiry import InquiryCreate
from app.api.inquiries import create_inquiry

from pydantic import BaseModel

from app.services.inquiry_analyzer import analyze_inquiry
from app.services.pricing_engine import calculate_price


router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    customer_name: str | None = None
    customer_phone: str | None = None
    customer_wechat: str | None = None


class ChatResponse(BaseModel):
    reply: str


@router.post(
    "",
    response_model=ChatResponse,
)
def chat(
    request: ChatRequest,
    db_session: Session = Depends(get_db_session),
) -> ChatResponse:

    analysis = analyze_inquiry(
        request.message
    )

    inquiry = InquiryCreate(
    message=request.message,
    customer_name=request.customer_name or "网站客户",
    customer_phone=request.customer_phone,
    customer_wechat=request.customer_wechat,
    source=None,
)

    result = create_inquiry(
        inquiry=inquiry,
        db_session=db_session,
    )

    extracted = analysis.extracted_information

    lines = []
    lines = []

    lines.append(
        "您好，我是 Jason 😊"
    )

    lines.append(
        "\n收到您的接送咨询："
    )


    if extracted.date:
        lines.append(
            f"📅 用车日期：{extracted.date}"
        )


    if extracted.pickup_time:
        lines.append(
            f"⏰ 接送时间：{extracted.pickup_time}"
        )


    # 机场显示逻辑

    if analysis.inquiry_type.value == "airport pickup":

        if extracted.airport:
            lines.append(
                f"✈ 接车地点：{extracted.airport}"
            )


    elif analysis.inquiry_type.value == "airport dropoff":

        if extracted.pickup_airport:
            lines.append(
                f"📍 上车地点：{extracted.pickup_airport}"
            )

        if extracted.dropoff_airport:
            lines.append(
                f"✈ 送往机场：{extracted.dropoff_airport}"
            )


    else:

        if extracted.airport:
            lines.append(
                f"✈ 机场：{extracted.airport}"
            )


    if (
        extracted.destination
        and not (
            extracted.pickup_airport
            and extracted.dropoff_airport
        )
    ):

        lines.append(
            f"📍 目的地：{extracted.destination}"
        )


    if extracted.passengers:

        lines.append(
            f"👥 乘客人数：{extracted.passengers}位"
        )


    if extracted.luggage:

        lines.append(
            f"🧳 行李：{extracted.luggage}"
        )


    # 价格计算

        # 价格计算
    try:

        price = None


        # 普通机场接送
        if extracted.airport and extracted.destination:

            price = calculate_price(
                extracted.airport,
                extracted.destination,
                extracted.pickup_time,
            )


        # 机场到机场
        elif (
            extracted.pickup_airport
            and extracted.dropoff_airport
        ):

            price = calculate_price(
                extracted.pickup_airport,
                extracted.dropoff_airport,
                extracted.pickup_time,
            )


        if price and price.minimum_amount:

            lines.append(
                f"💰 预估费用：${price.minimum_amount} - ${price.maximum_amount}"
            )


    except Exception:

        pass



    missing = []


    mapping = {

        "date": "📅 用车日期",

        "pickup_time": "⏰ 接送时间",

        "airport": "✈ 机场",

        "destination": "📍 目的地",

        "passenger_count": "👥 乘客人数",

        "luggage_details": "🧳 行李数量",

        "flight_information": "✈ 航班号",

        "child_seat_requirements": "👶 儿童座椅需求",

        "special_requests": "📝 其他特殊需求",

    }


    for item in analysis.missing_information:

        if item in mapping:

            missing.append(
                mapping[item]
            )


    if missing:

        lines.append(
            "\n为了确认行程，还需要："
        )


        for item in missing:

            lines.append(
                f"• {item}"
            )


    lines.append(
        "\n最终价格和档期需要 Jason 确认。"
    )


    lines.append(
        "谢谢您的咨询。"
    )


    
    return ChatResponse(
        reply="\n".join(lines)
)
@router.get("/history/{customer_id}")
def chat_history(
    customer_id: UUID,
    db_session: Session = Depends(get_db_session),
):

    conversations = (
        db_session.query(Conversation)
        .filter(
            Conversation.customer_id == customer_id,
            Conversation.customer_visible == True
        )
        .order_by(
            Conversation.created_at
        )
        .all()
    )


    return [
        {
            "sender": item.sender_type,
            "message": item.message_text,
        }
        for item in conversations
    ]