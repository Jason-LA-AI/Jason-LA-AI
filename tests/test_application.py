"""Smoke tests for the application skeleton."""

from unittest.mock import MagicMock
from uuid import UUID

from fastapi.testclient import TestClient

from app.main import app
from app.api import dashboard as dashboard_module
from app.models.conversation import Conversation
from app.models.customer import Customer
from app.models.lead import Lead
from app.database.seed import DEVELOPMENT_INQUIRIES
from app.services.inquiry_analyzer import analyze_inquiry


def test_application_metadata() -> None:
    assert app.title == "Jason-LA-AI"
    assert app.version == "0.1.0"


def test_public_brand_pages_render(client: TestClient) -> None:
    home = client.get("/")
    gallery = client.get("/gallery")

    assert home.status_code == 200
    assert "Meet Jason" in home.text
    assert "/gallery" in home.text
    assert gallery.status_code == 200
    assert "Service Gallery" in gallery.text
    assert 'loading="lazy"' in gallery.text


def test_private_car_service_page_render_and_seo(client: TestClient) -> None:
    response = client.get("/private-car-service")

    assert response.status_code == 200
    assert "Private Car Service in Los Angeles" in response.text
    assert "Request a Custom Quote" in response.text
    assert (
        "Private car service in Los Angeles for airport transfers, events, "
        "shopping, family trips and customized transportation."
        in response.text
    )
    assert '<link rel="canonical"' in response.text


def test_sitemap_includes_private_car_service(client: TestClient) -> None:
    response = client.get("/sitemap.xml")

    assert response.status_code == 200
    assert "/private-car-service</loc>" in response.text


def test_ont_airport_transportation_page_render_and_seo(client: TestClient) -> None:
    response = client.get("/ont-airport-transportation")

    assert response.status_code == 200
    assert response.text.count("<h1>") == 1
    assert "<h1>ONT Airport Transportation</h1>" in response.text
    assert "Request Your ONT Airport Ride" in response.text
    assert "Real Trip Stories" in response.text
    assert (
        "Reliable ONT Airport Transportation with a local private driver. "
        "Airport pickup and drop-off service for Ontario, Chino, Eastvale, "
        "Rowland Heights and surrounding areas."
        in response.text
    )
    assert '<link rel="canonical"' in response.text


def test_sitemap_includes_ont_airport_transportation(client: TestClient) -> None:
    response = client.get("/sitemap.xml")

    assert response.status_code == 200
    assert "/ont-airport-transportation</loc>" in response.text


def test_student_airport_pickup_page_render_and_seo(client: TestClient) -> None:
    response = client.get("/student-airport-pickup")

    assert response.status_code == 200
    assert response.text.count("<h1>") == 1
    assert "<h1>Student Airport Pickup in Los Angeles</h1>" in response.text
    assert "Ontario International Airport (ONT)" in response.text
    assert "Los Angeles International Airport (LAX)" in response.text
    assert "Hollywood Burbank Airport (BUR)" in response.text
    assert 'href="/stories"' in response.text
    assert 'href="/quote">Request a Quote</a>' in response.text
    assert (
        "Reliable student airport pickup service in Los Angeles for international "
        "students and families. Serving ONT, LAX and surrounding areas."
        in response.text
    )
    assert (
        "Student Airport Pickup in Los Angeles | International Student "
        "Transportation | Jason in Los Angeles"
        in response.text
    )
    assert '<link rel="canonical"' in response.text
    assert '<meta property="og:title"' in response.text
    assert '<meta property="og:description"' in response.text
    assert '<meta property="og:url"' in response.text
    assert "ont-terminal2-baggage-claim-800.webp" in response.text


def test_sitemap_includes_student_airport_pickup(client: TestClient) -> None:
    response = client.get("/sitemap.xml")

    assert response.status_code == 200
    assert "/student-airport-pickup</loc>" in response.text


def test_contact_channels_and_public_images_render(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setitem(
        dashboard_module.templates.env.globals,
        "phone_number",
        "+16265550123",
    )
    contact = client.get("/contact")
    ont = client.get("/ont-airport-transportation")
    private_car = client.get("/private-car-service")

    assert contact.status_code == 200
    assert "WeChat 微信" in contact.text
    assert "For travelers from Taiwan / 台湾旅客可通过 LINE 联系 Jason" in contact.text
    assert 'alt="WeChat QR code to contact Jason"' in contact.text
    assert 'alt="LINE QR code to contact Jason"' in contact.text
    assert 'href="tel:+16265550123"' in contact.text
    assert 'href="/quote">Get a Quote</a>' in contact.text
    assert 'loading="lazy"' in contact.text
    assert ont.status_code == 200
    assert "ont-arrivals-rainbow-800.webp" in ont.text
    assert "ont-terminal2-baggage-claim-800.webp" in ont.text
    assert private_car.status_code == 200
    assert "costco-shopping-sunset-800.webp" in private_car.text
    assert "sonesta-hotel-transfer-800.webp" in private_car.text

    for path in (
        "/static/images/contact/wechat-qr.png",
        "/static/images/contact/wechat-qr.webp",
        "/static/images/contact/line-qr.png",
        "/static/images/contact/line-qr-800.webp",
        "/static/images/service/costco-shopping-sunset-800.webp",
        "/static/images/service/sonesta-hotel-transfer-800.webp",
        "/static/images/service/ont-arrivals-rainbow-800.webp",
        "/static/images/service/ont-terminal2-baggage-claim-800.webp",
    ):
        response = client.get(path)
        assert response.status_code == 200
        assert response.content


def test_create_inquiry(
    client: TestClient,
    database_session: MagicMock,
    telegram_mock: MagicMock,
) -> None:
    response = client.post(
        "/api/v1/inquiries",
        json={
            "message": "你好，请问ONT接机多少钱？",
            "customer_name": "Test Customer",
            "source": "Xiaohongshu",
        },
    )

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
    telegram_mock.assert_called_once()


def test_create_inquiry_succeeds_when_telegram_delivery_fails(
    client: TestClient,
    database_session: MagicMock,
    telegram_mock: MagicMock,
) -> None:
    telegram_mock.side_effect = RuntimeError("notification unavailable")

    response = client.post(
        "/api/v1/inquiries",
        json={
            "message": "ONT airport pickup to Walnut",
            "customer_name": "Test Customer",
            "source": "Website",
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == "inquiry received"
    database_session.commit.assert_called_once()
    database_session.rollback.assert_not_called()
    telegram_mock.assert_called_once()


def test_create_inquiry_rejects_unknown_source(client: TestClient) -> None:
    response = client.post(
        "/api/v1/inquiries",
        json={"message": "Airport pickup", "source": "Unknown"},
    )

    assert response.status_code == 422


def test_dashboard_renders_empty_state(
    client: TestClient,
    database_session: MagicMock,
) -> None:
    database_session.execute.return_value.all.return_value = []
    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "No inquiries yet" in response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-robots-tag"] == "noindex, nofollow"


def test_dashboard_requires_configured_credentials(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(dashboard_module.settings, "dashboard_username", "jason")
    monkeypatch.setattr(dashboard_module.settings, "dashboard_password", "secret")

    denied = client.get("/dashboard")
    allowed = client.get(
        "/dashboard",
        auth=("jason", "secret"),
    )

    assert denied.status_code == 401
    assert denied.headers["www-authenticate"] == 'Basic realm="Jason Dashboard"'
    assert allowed.status_code == 200


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
