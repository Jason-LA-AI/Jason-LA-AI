"""Authenticated Telegram callback webhook endpoint."""

from datetime import datetime, timezone
import logging
import secrets
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.database.session import get_db_session
from app.models.approval import Approval
from app.models.conversation import Conversation
from app.models.order import Order
from app.models.quote import Quote
from app.services.telegram_notifier import send_telegram_text


router = APIRouter()
logger = logging.getLogger(__name__)


def _verify_webhook_request(secret_header: str | None) -> None:
    """Authenticate the secret header configured with Telegram setWebhook."""

    expected_secret = settings.telegram_webhook_secret
    if not expected_secret:
        if settings.is_production:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Telegram webhook is not configured",
            )
        return
    if not secret_header or not secrets.compare_digest(secret_header, expected_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Telegram webhook secret",
        )


def _chat_id(payload: dict) -> str | None:
    callback = payload.get("callback_query") or {}
    message = callback.get("message") or payload.get("message") or {}
    chat = message.get("chat") or {}
    value = chat.get("id")
    return str(value) if value is not None else None


def _verify_authorized_chat(payload: dict) -> None:
    expected_chat_id = settings.telegram_chat_id
    if expected_chat_id and _chat_id(payload) != str(expected_chat_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Telegram chat is not authorized",
        )


@router.post("/webhook")
async def telegram_webhook(
    payload: dict,
    telegram_secret: str | None = Header(
        default=None,
        alias="X-Telegram-Bot-Api-Secret-Token",
    ),
    db_session: Session = Depends(get_db_session),
) -> dict[str, object]:
    """Handle authenticated updates without logging customer content."""

    _verify_webhook_request(telegram_secret)
    _verify_authorized_chat(payload)
    logger.info("Telegram update received")

    callback = payload.get("callback_query")
    if not callback:
        return _handle_price_message(payload.get("message"), db_session)

    data = callback.get("data")
    if not isinstance(data, str):
        return {"ok": True}

    try:
        action, approval_id_text = data.split(":", 1)
        approval_id = UUID(approval_id_text)
    except (TypeError, ValueError):
        return {"ok": True}

    if action not in {"approve", "modify", "reject"}:
        return {"ok": True}

    approval = db_session.query(Approval).filter(Approval.id == approval_id).first()
    if approval is None or approval.status != "PENDING":
        return {"ok": True}

    now = datetime.now(timezone.utc)
    if action == "approve":
        _approve(approval, db_session, now)
    elif action == "modify":
        approval.decision_value = {"action": "WAITING_FOR_PRICE"}
        approval.decision_by = "Jason"
        db_session.commit()
        send_telegram_text(
            _chat_id(payload) or "",
            "✏ 请按以下格式发送最终报价：\n"
            f"price:{approval.id}:180",
        )
    else:
        approval.status = "DECLINED"
        approval.decision_by = "Jason"
        approval.decided_at = now

    if action != "modify":
        db_session.commit()
    logger.info("Telegram approval action processed")
    return {"ok": True, "approval_status": approval.status}


def _handle_price_message(message: object, db_session: Session) -> dict[str, object]:
    if not isinstance(message, dict):
        return {"ok": True}

    text = message.get("text")
    try:
        command, approval_id_text, price_text = str(text).split(":", 2)
        if command.lower() != "price":
            raise ValueError
        approval_id = UUID(approval_id_text)
        price = float(price_text)
        if price <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return {"ok": True}

    approval = (
        db_session.query(Approval)
        .filter(
            Approval.id == approval_id,
            Approval.status == "PENDING",
            Approval.decision_value["action"].astext == "WAITING_FOR_PRICE",
        )
        .first()
    )
    if approval is None or approval.quote_id is None:
        return {"ok": True}

    quote = db_session.query(Quote).filter(Quote.id == approval.quote_id).first()
    if quote is None:
        return {"ok": True}

    quote.final_quoted_amount = price
    quote.status = "APPROVED"
    approval.decision_value = {"action": "PRICE_UPDATED", "final_price": price}
    approval.status = "APPROVED"
    approval.decision_by = "Jason"
    approval.decided_at = datetime.now(timezone.utc)
    db_session.commit()
    send_telegram_text(
        _chat_id({"message": message}) or "",
        f"✅ 价格修改成功\n\n最终报价：${price:g}",
    )
    logger.info("Telegram approval price updated")
    return {"ok": True, "approval_status": approval.status}


def _approve(approval: Approval, db_session: Session, now: datetime) -> None:
    approval.status = "APPROVED"
    approval.decision_by = "Jason"
    approval.decided_at = now

    quote = None
    if approval.quote_id is not None:
        quote = db_session.query(Quote).filter(Quote.id == approval.quote_id).first()
        if quote is not None:
            if quote.suggested_amount:
                quote.final_quoted_amount = quote.suggested_amount
            quote.status = "APPROVED"
            quote.approved_at = now

    order = db_session.query(Order).filter(Order.id == approval.order_id).first()
    if order is None or quote is None:
        return

    message = (
        "您好，我是 Jason 😊\n\n您的接送报价已经确认：\n\n"
        f"📅 日期：{order.service_date}\n"
        f"⏰ 时间：{order.pickup_at}\n"
        f"✈ 机场：{order.airport_code}\n"
        f"📍 目的地：{order.destination}\n"
        f"👥 人数：{order.passenger_count}\n"
        f"💰 费用：${quote.final_quoted_amount}\n"
        f"车辆：{order.vehicle_name}\n\n请回复确认预约。\n\n谢谢！"
    )
    db_session.add(
        Conversation(
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
    )
