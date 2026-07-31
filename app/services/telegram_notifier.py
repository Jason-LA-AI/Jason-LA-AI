import os

import requests
from dotenv import load_dotenv


load_dotenv()


BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")



def _send_message(
    text: str,
    reply_markup: dict | None = None,
) -> None:

    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram configuration missing")
        return


    url = (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/sendMessage"
    )


    payload = {
        "chat_id": CHAT_ID,
        "text": text,
    }


    if reply_markup:
        payload["reply_markup"] = reply_markup


    response = requests.post(
        url,
        json=payload,
        timeout=10,
    )

    response.raise_for_status()

    print("Telegram notification sent")



def send_telegram_notification(
    message: str,
    approval_id: str | None = None,
) -> None:
    """
    Send Telegram message.
    Supports optional approval buttons.
    """


    if approval_id:

        reply_markup = {
            "inline_keyboard": [
                [
                    {
                        "text": "✅ 使用AI价格",
                        "callback_data": (
                            f"approve:{approval_id}"
                        ),
                    }
                ],
                [
                    {
                        "text": "✏ 修改价格",
                        "callback_data": (
                            f"modify:{approval_id}"
                        ),
                    }
                ],
                [
                    {
                        "text": "❌ 拒绝订单",
                        "callback_data": (
                            f"reject:{approval_id}"
                        ),
                    }
                ],
            ]
        }


        _send_message(
            message,
            reply_markup,
        )


    else:

        _send_message(message)



def send_approval_notification(
    approval_id: str,
    message: str,
) -> None:
    """
    Send approval request with buttons.
    """

    send_telegram_notification(
        message=message,
        approval_id=approval_id,
    )



def send_telegram_text(
    chat_id: str,
    text: str,
) -> None:
    """
    Send plain Telegram message.
    """


    if not BOT_TOKEN:
        print("Telegram bot token missing")
        return


    url = (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/sendMessage"
    )


    payload = {
        "chat_id": chat_id,
        "text": text,
    }


    response = requests.post(
        url,
        json=payload,
        timeout=10,
    )


    response.raise_for_status()