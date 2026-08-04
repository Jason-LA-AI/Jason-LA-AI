"""Pure Telegram inline keyboard payload construction."""

from __future__ import annotations

from typing import TypedDict


ACTION_TOKEN_REQUIRED = "ACTION_TOKEN_REQUIRED"


class TelegramKeyboardError(ValueError):
    """Business error raised when keyboard data cannot be built safely."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class InlineKeyboardButton(TypedDict):
    text: str
    callback_data: str


def build_approval_keyboard(token: str) -> list[list[InlineKeyboardButton]]:
    """Build approve and decline callback buttons from one plaintext token."""

    if not isinstance(token, str) or not token or token.strip() != token:
        raise TelegramKeyboardError(ACTION_TOKEN_REQUIRED)

    return [
        [
            {
                "text": "Approve",
                "callback_data": f"APPROVE:{token}",
            },
            {
                "text": "Decline",
                "callback_data": f"DECLINE:{token}",
            },
        ]
    ]
