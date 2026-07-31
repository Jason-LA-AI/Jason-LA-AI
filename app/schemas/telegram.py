from pydantic import BaseModel


class TelegramWebhook(BaseModel):
    update_id: int | None = None
    message: dict | None = None
    callback_query: dict | None = None