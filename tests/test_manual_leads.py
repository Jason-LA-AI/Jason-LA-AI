"""Tests for manual lead intake from the internal dashboard."""

from unittest.mock import MagicMock
from uuid import UUID

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from app.api import dashboard as dashboard_module
from app.models.customer import Customer
from app.models.lead import Lead
from app.schemas.manual_lead import ManualLeadCreate, ManualLeadStatus
from app.services.manual_lead_service import create_manual_lead, update_manual_lead_status


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "customer_name": "Manual Customer",
        "source": "PHONE",
        "status": "NEW",
        "phone": "626-555-0100",
        "intent": "AIRPORT_PICKUP",
        "service_date": "2026-09-01",
        "airport": "lax",
        "pickup": None,
        "destination": "Rowland Heights",
        "notes": "Two passengers",
    }
    payload.update(overrides)
    return payload


def test_manual_lead_requires_contact() -> None:
    with pytest.raises(ValidationError, match="Provide a phone, WeChat, or social contact"):
        ManualLeadCreate.model_validate(
            _payload(phone=None, wechat=None, social_contact=None)
        )


def test_manual_lead_service_creates_customer_and_lead() -> None:
    db = MagicMock()
    request = ManualLeadCreate.model_validate(_payload())

    lead = create_manual_lead(db, request)

    added = [call.args[0] for call in db.add.call_args_list]
    customer = next(record for record in added if isinstance(record, Customer))
    assert customer.source == "PHONE"
    assert customer.primary_contact == "626-555-0100"
    assert lead.source == "PHONE"
    assert lead.status == "NEW"
    assert lead.intake_method == "MANUAL"
    assert lead.analysis_result["extracted_information"]["airport"] == "LAX"
    assert lead.route_summary == "LAX → Rowland Heights"
    db.commit.assert_called_once()


def test_dashboard_manual_lead_endpoint_does_not_notify(
    client: TestClient,
    database_session: MagicMock,
    telegram_mock: MagicMock,
) -> None:
    response = client.post("/dashboard/leads", json=_payload())

    assert response.status_code == 201
    assert response.json()["status"] == "NEW"
    database_session.commit.assert_called_once()
    telegram_mock.assert_not_called()


def test_dashboard_renders_manual_lead_form_and_list_columns(
    client: TestClient,
    database_session: MagicMock,
) -> None:
    database_session.execute.return_value.all.return_value = []

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "New Lead" in response.text
    assert 'name="source"' in response.text
    assert 'value="PHONE"' in response.text
    assert 'value="WECHAT"' in response.text
    assert "Lead list" in response.text


def test_dashboard_manual_lead_endpoint_requires_dashboard_auth(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(dashboard_module.settings, "dashboard_username", "jason")
    monkeypatch.setattr(dashboard_module.settings, "dashboard_password", "secret")

    denied = client.post("/dashboard/leads", json=_payload())
    allowed = client.post(
        "/dashboard/leads",
        json=_payload(source="WECHAT", phone=None, wechat="wechat-id"),
        auth=("jason", "secret"),
    )

    assert denied.status_code == 401
    assert allowed.status_code == 201


@pytest.mark.parametrize(
    ("dashboard_status", "database_status"),
    [
        ("NEW", "NEW"),
        ("QUOTED", "QUOTED"),
        ("WAITING", "FOLLOW_UP"),
        ("CONFIRMED", "CONVERTED"),
        ("COMPLETED", "CONVERTED"),
        ("LOST", "LOST"),
    ],
)
def test_update_manual_lead_status_uses_existing_columns(
    dashboard_status: str,
    database_status: str,
) -> None:
    db = MagicMock()
    lead = Lead(status="NEW", analysis_result={"existing": "value"})

    update_manual_lead_status(db, lead, ManualLeadStatus(dashboard_status))

    assert lead.status == database_status
    assert lead.analysis_result == {
        "existing": "value",
        "manual_status": dashboard_status,
    }
    db.commit.assert_called_once()


def test_dashboard_status_endpoint_saves_immediately(
    client: TestClient,
    database_session: MagicMock,
) -> None:
    lead = Lead(status="NEW", analysis_result={})
    lead.id = UUID("11111111-1111-1111-1111-111111111111")
    database_session.get.return_value = lead

    response = client.patch(
        f"/dashboard/leads/{lead.id}/status",
        json={"status": "COMPLETED"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"
    assert lead.status == "CONVERTED"
    assert lead.analysis_result["manual_status"] == "COMPLETED"
    database_session.commit.assert_called_once()


def test_dashboard_status_endpoint_rejects_invalid_status(client: TestClient) -> None:
    response = client.patch(
        "/dashboard/leads/11111111-1111-1111-1111-111111111111/status",
        json={"status": "CANCELLED"},
    )

    assert response.status_code == 422
