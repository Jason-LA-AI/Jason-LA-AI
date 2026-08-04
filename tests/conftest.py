"""Shared pytest fixtures that isolate tests from databases and networks."""

from collections.abc import Generator
import ipaddress
import os
import socket
from unittest.mock import MagicMock

# Establish a safe test environment before importing any application module.
os.environ["APP_ENVIRONMENT"] = "test"
os.environ["DEBUG"] = "false"
os.environ["DATABASE_URL"] = (
    "postgresql+psycopg://test_user:unused@invalid.example:5432/test_db"
)
os.environ.pop("TELEGRAM_BOT_TOKEN", None)
os.environ.pop("TELEGRAM_CHAT_ID", None)

import pytest
import requests
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api import inquiries as inquiries_api
from app.database.session import get_db_session
from app.main import app
from app.services import telegram_notifier
from app.services.telegram_provider import TelegramProvider


@pytest.fixture(autouse=True)
def block_external_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail tests before any outbound HTTP, SMTP, SMS, or webhook connection."""

    original_socket_connect = socket.socket.connect

    def blocked_request(
        self: requests.Session,
        method: str,
        url: str,
        *args: object,
        **kwargs: object,
    ) -> None:
        del self, method, url, args, kwargs
        raise AssertionError("External HTTP requests are disabled during tests.")

    def blocked_socket_connect(
        self: socket.socket,
        address: object,
    ) -> None:
        if isinstance(address, tuple) and address:
            host = str(address[0])
            try:
                if ipaddress.ip_address(host).is_loopback:
                    original_socket_connect(self, address)
                    return
            except ValueError:
                if host.lower() == "localhost":
                    original_socket_connect(self, address)
                    return
        raise AssertionError("External network connections are disabled during tests.")

    monkeypatch.setattr(requests.Session, "request", blocked_request)
    monkeypatch.setattr(socket.socket, "connect", blocked_socket_connect)


@pytest.fixture(autouse=True)
def telegram_mock(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Replace all currently reachable Telegram delivery paths with mocks."""

    approval_notification = MagicMock(name="send_approval_notification")
    telegram_send = MagicMock(name="send_telegram_message")

    monkeypatch.setattr(
        inquiries_api,
        "send_approval_notification",
        approval_notification,
    )
    monkeypatch.setattr(
        telegram_notifier,
        "_send_message",
        telegram_send,
    )
    monkeypatch.setattr(
        TelegramProvider,
        "send_message",
        telegram_send,
    )

    return approval_notification


@pytest.fixture
def database_session() -> MagicMock:
    """Return a SQLAlchemy-compatible session mock for API tests."""

    return MagicMock(spec=Session)


@pytest.fixture
def client(database_session: MagicMock) -> Generator[TestClient, None, None]:
    """Provide a TestClient with the database dependency safely overridden."""

    def override_db_session() -> Generator[Session, None, None]:
        yield database_session

    app.dependency_overrides[get_db_session] = override_db_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db_session, None)
