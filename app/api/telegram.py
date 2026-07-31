"""Telegram callback webhook endpoint."""

from datetime import datetime, timezone
from uuid import UUID, uuid4
from app.models.order import Order

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db_session
from app.models.approval import Approval
from app.models.quote import Quote
from app.models.conversation import Conversation
from app.services.telegram_notifier import send_telegram_text


router = APIRouter()


@router.post("/webhook")
async def telegram_webhook(
    payload: dict,
    db_session: Session = Depends(get_db_session),
):

    print("Telegram update:")
    print(payload)


    callback = payload.get(
        "callback_query"
    )


    # 普通文字消息
    if not callback:

        message = payload.get(
            "message"
        )


        if message:

            text = message.get(
                "text"
            )


            print(
                "Telegram message:",
                text
            )


            try:

                price = float(text)


                approval = (
                    db_session.query(Approval)
                    .filter(
                        Approval.decision_value["action"].astext
                        == "WAITING_FOR_PRICE"
                    )
                    .first()
                )


                if approval and approval.quote_id:

                    quote = (
                        db_session.query(Quote)
                        .filter(
                            Quote.id == approval.quote_id
                        )
                        .first()
                    )


                    if quote:

                        quote.final_quoted_amount = price
                        quote.status = "APPROVED"


                        approval.decision_value = {
                            "action": "PRICE_UPDATED",
                            "final_price": price,
                        }


                        approval.status = "APPROVED"
                        approval.decided_at = datetime.now(
                            timezone.utc
                        )


                        db_session.commit()


                        send_telegram_text(
                            str(
                                message["chat"]["id"]
                            ),
                            f"""
✅ 价格修改成功

最终报价:
${price}
"""
                        )


                        print(
                            f"Price updated: {price}"
                        )


            except ValueError:

                print(
                    "Not a price input"
                )


        return {
            "ok": True
        }



    data = callback.get(
        "data"
    )


    if not data:

        return {
            "ok": True
        }


    action, approval_id = data.split(
        ":",
        1
    )


    print(
        f"Telegram action: {action}"
    )



    approval = (
        db_session.query(Approval)
        .filter(
            Approval.id == UUID(approval_id)
        )
        .first()
    )


    if not approval:

        print(
            "Approval not found"
        )

        return {
            "ok": True
        }



    now = datetime.now(
        timezone.utc
    )


    if action == "approve":

        approval.status = "APPROVED"
        approval.decision_by = "Jason"
        approval.decided_at = now


        if approval.quote_id:

            quote = (
                db_session.query(Quote)
                .filter(
                    Quote.id == approval.quote_id
                )
                .first()
            )


            if quote:

                if quote.suggested_amount:
                    quote.final_quoted_amount = quote.suggested_amount

            quote.status = "APPROVED"
            quote.approved_at = now
        order = (
            db_session.query(Order)
            .filter(
                Order.id == approval.order_id
            )
            .first()
        )

        if order:

            message = f"""
您好，我是 Jason 😊

您的接送报价已经确认：

📅 日期：
{order.service_date}

⏰ 时间：
{order.pickup_at}

✈ 机场：
{order.airport_code}

📍 目的地：
{order.destination}

👥 人数：
{order.passenger_count}

💰 费用：
${quote.final_quoted_amount}

车辆：
{order.vehicle_name}

请回复确认预约。

谢谢！
"""

            customer_message = Conversation(
                id=uuid4(),
                customer_id=order.customer_id,
                lead_id=order.lead_id,
                order_id=order.id,
                channel="GOOGLE_WEBSITE",
                direction="OUTBOUND",
                sender_type="JASON",
                message_text=message,
                customer_visible=True,
                ai_generated=False,
                delivery_status="SENT",
            )

            db_session.add(customer_message)



        print(
            f"Approved: {approval_id}"
        )



    elif action == "modify":

        approval.decision_value = {
            "action": "WAITING_FOR_PRICE"
        }


        approval.decision_by = "Jason"
        approval.decided_at = now


        db_session.commit()


        send_telegram_text(
            str(
                callback["message"]["chat"]["id"]
            ),
            """
✏ 请发送最终报价：

例如：
180
"""
        )


        print(
            f"Waiting price input: {approval_id}"
        )



    elif action == "reject":

        approval.status = "DECLINED"
        approval.decision_by = "Jason"
        approval.decided_at = now


        print(
            f"Rejected: {approval_id}"
        )



    db_session.commit()


    return {
        "ok": True,
        "approval_status": approval.status,
    }