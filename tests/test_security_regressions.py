"""Regression coverage for public-boundary security controls."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.api import dashboard as dashboard_module
from app.api import telegram as telegram_module


def test_production_telegram_webhook_fails_closed_without_secret(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(telegram_module.settings, "app_environment", "production")
    monkeypatch.setattr(telegram_module.settings, "telegram_webhook_secret", None)

    response = client.post("/api/v1/telegram/webhook", json={})

    assert response.status_code == 503


def test_telegram_webhook_requires_matching_secret_and_chat(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(telegram_module.settings, "telegram_webhook_secret", "test-secret")
    monkeypatch.setattr(telegram_module.settings, "telegram_chat_id", "12345")

    missing_secret = client.post(
        "/api/v1/telegram/webhook",
        json={"message": {"chat": {"id": 12345}, "text": "hello"}},
    )
    wrong_chat = client.post(
        "/api/v1/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
        json={"message": {"chat": {"id": 99999}, "text": "hello"}},
    )
    accepted = client.post(
        "/api/v1/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
        json={"message": {"chat": {"id": 12345}, "text": "hello"}},
    )

    assert missing_secret.status_code == 401
    assert wrong_chat.status_code == 403
    assert accepted.status_code == 200
    assert accepted.json() == {"ok": True}


def test_chat_history_requires_dashboard_auth(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(dashboard_module.settings, "dashboard_username", "jason")
    monkeypatch.setattr(dashboard_module.settings, "dashboard_password", "secret")
    customer_id = uuid4()

    denied = client.get(f"/api/v1/chat/history/{customer_id}")
    allowed = client.get(
        f"/api/v1/chat/history/{customer_id}",
        auth=("jason", "secret"),
    )

    assert denied.status_code == 401
    assert allowed.status_code == 200


def test_public_inquiry_rejects_oversized_fields(client: TestClient) -> None:
    inquiry = client.post(
        "/api/v1/inquiries",
        json={"message": "x" * 4001},
    )
    chat = client.post(
        "/api/v1/chat",
        json={"message": "x" * 4001},
    )

    assert inquiry.status_code == 422
    assert chat.status_code == 422
