"""Regression coverage for quote-request source tracking."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.dashboard import _display_source
from app.models.notification import Notification
from app.schemas.quote_request import QuoteRequestCreate
from app.services.telegram_adapter import _render_quote_request_review


def _request_payload(source: str) -> dict[str, object]:
    return {
        "estimate_id": "11111111-1111-1111-1111-111111111111",
        "customer_name": "Test Customer",
        "phone": "5551234567",
        "email": None,
        "preferred_contact_method": "SMS",
        "source": source,
        "estimate_acceptance": True,
    }


@pytest.mark.parametrize(
    "source",
    ["WEBSITE", "XIAOHONGSHU", "FACEBOOK", "GOOGLE", "REFERRAL", "OTHER"],
)
def test_quote_request_accepts_supported_sources(source: str) -> None:
    request = QuoteRequestCreate.model_validate(_request_payload(source))
    assert request.source.value == source


@pytest.mark.parametrize("source", ["INSTAGRAM", "DIRECT"])
def test_quote_request_rejects_unknown_source(source: str) -> None:
    with pytest.raises(ValidationError):
        QuoteRequestCreate.model_validate(_request_payload(source))


def test_dashboard_displays_distinct_google_and_website_sources() -> None:
    assert _display_source("WEBSITE") == "Website"
    assert _display_source("GOOGLE") == "Google Search"


@pytest.mark.parametrize(
    ("query_source", "expected_source"),
    [
        ("facebook", "FACEBOOK"),
        ("XIAOHONGSHU", "XIAOHONGSHU"),
        ("Google", "GOOGLE"),
        ("direct", "WEBSITE"),
        ("website", "WEBSITE"),
    ],
)
def test_quote_source_query_prefills_only_whitelisted_source(
    client: TestClient,
    query_source: str,
    expected_source: str,
) -> None:
    response = client.get(f"/quote?source={query_source}")
    script = client.get("/static/quote.js")

    assert response.status_code == 200
    assert script.status_code == 200
    assert f'{query_source.lower()}: "{expected_source}"' in script.text
    assert 'document.getElementById("source").value = selected' in script.text


@pytest.mark.parametrize("source", ["facebook", "direct", "website", "facebook123"])
def test_quote_source_query_has_no_load_side_effect(
    client: TestClient,
    database_session,
    source: str,
) -> None:
    response = client.get(f"/quote?source={source}")
    script = client.get("/static/quote.js")

    assert response.status_code == 200
    assert 'const allowedSources = { facebook: "FACEBOOK", xiaohongshu: "XIAOHONGSHU", google: "GOOGLE", direct: "WEBSITE", website: "WEBSITE" }' in script.text
    database_session.add.assert_not_called()
    database_session.commit.assert_not_called()


def test_legacy_notification_without_source_still_renders() -> None:
    notification = Notification(
        channel="TELEGRAM",
        status="PENDING",
        template_key="QUOTE_REQUEST_REVIEW",
        payload={
            "approval_id": "approval",
            "order_id": "order",
            "quote_id": "quote",
            "estimate_id": "estimate",
            "service_type": "AIRPORT_PICKUP",
            "route_summary": "LAX to Rowland Heights",
        },
        attempt_count=0,
    )
    assert "Source: UNKNOWN" in _render_quote_request_review(notification)
