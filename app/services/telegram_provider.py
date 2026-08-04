"""Network-free Telegram provider abstraction."""

from __future__ import annotations

from typing import Any


class TelegramProvider:
    """Mock provider interface for future Telegram delivery implementations."""

    def send_message(
        self,
        message: str,
        reply_markup: list[list[dict[str, str]]] | None = None,
    ) -> dict[str, Any]:
        """Return a simulated delivery result without retaining message data."""

        del message, reply_markup
        return {
            "provider": "TELEGRAM_MOCK",
            "message_id": "mock-id",
        }
