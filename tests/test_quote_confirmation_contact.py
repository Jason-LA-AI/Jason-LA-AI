"""Conditional urgent contact display on quote confirmation."""

from fastapi.testclient import TestClient
import pytest

from app.api import dashboard as dashboard_module


def test_confirmation_displays_configured_urgent_phone(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        dashboard_module.templates.env.globals,
        "phone_number",
        "+1 626-555-0100",
    )

    response = client.get("/quote/confirmation")

    assert response.status_code == 200
    assert "Need to update your trip urgently?" in response.text
    assert "Call or text Jason:" in response.text
    assert "+1 626-555-0100" in response.text


def test_confirmation_hides_urgent_contact_without_phone(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        dashboard_module.templates.env.globals,
        "phone_number",
        None,
    )

    response = client.get("/quote/confirmation")

    assert response.status_code == 200
    assert "Need to update your trip urgently?" not in response.text
