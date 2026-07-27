"""Smoke tests for the application skeleton."""

from collections.abc import Generator
from unittest.mock import MagicMock
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.session import get_db_session
from app.main import app
from app.models.conversation import Conversation
from app.models.customer import Customer
from app.models.lead import Lead
from app.database.seed import DEVELOPMENT_INQUIRIES
from app.services.inquiry_analyzer import analyze_inquiry


client = TestClient(app)


def test_application_metadata() -> None:
    assert app.title == "Jason-LA-AI"
    assert app.version == "0.1.0"


def test_create_inquiry() -> None:
    database_session = MagicMock(spec=Session)

    def override_db_session() -> Generator[Session, None, None]:
        yield database_session

    app.dependency_overrides[get_db_session] = override_db_session
    try:
        response = client.post(
            "/api/v1/inquiries",
            json={
                "message": "你好，请问ONT接机多少钱？",
                "customer_name": "Test Customer",
                "source": "Xiaohongshu",
            },
        )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "inquiry received"
    assert UUID(payload["inquiry_id"])
    assert payload["received_at"].endswith("Z") or "+00:00" in payload["received_at"]
    database_session.commit.assert_called_once()

    records = database_session.add_all.call_args.args[0]
    customer = next(record for record in records if isinstance(record, Customer))
    lead = next(record for record in records if isinstance(record, Lead))
    conversation = next(
        record for record in records if isinstance(record, Conversation)
    )
    assert customer.preferred_language == "zh-CN"
    assert lead.analysis_result["detected_language"] == "zh-CN"
    assert conversation.message_text == "你好，请问ONT接机多少钱？"


def test_create_inquiry_rejects_unknown_source() -> None:
    response = client.post(
        "/api/v1/inquiries",
        json={"message": "Airport pickup", "source": "Unknown"},
    )

    assert response.status_code == 422


def test_dashboard_renders_empty_state() -> None:
    database_session = MagicMock(spec=Session)
    database_session.execute.return_value.all.return_value = []

    def override_db_session() -> Generator[Session, None, None]:
        yield database_session

    app.dependency_overrides[get_db_session] = override_db_session
    try:
        response = client.get("/dashboard")
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert response.status_code == 200
    assert "No inquiries yet" in response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-robots-tag"] == "noindex, nofollow"


def test_development_seed_analysis_expectations() -> None:
    for seed in DEVELOPMENT_INQUIRIES:
        analysis = analyze_inquiry(seed.message)
        assert analysis.detected_language.value == seed.expected_language
        assert analysis.risk_level.value == seed.expected_risk
        assert analysis.vehicle_assessment.value == seed.expected_vehicle_assessment
        assert analysis.recommended_action.value == seed.expected_action

    taiwan = analyze_inquiry(DEVELOPMENT_INQUIRIES[0].message)
    assert taiwan.extracted_information.airport == "ONT"
    assert taiwan.extracted_information.destination == "Rowland Heights"

    capacity_risk = analyze_inquiry(DEVELOPMENT_INQUIRIES[2].message)
    assert capacity_risk.extracted_information.passengers == 5
    assert capacity_risk.extracted_information.luggage == "6 large suitcases"
