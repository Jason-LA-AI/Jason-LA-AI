"""Regression coverage for quote-request source tracking."""

import pytest
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


def test_quote_request_rejects_unknown_source() -> None:
    with pytest.raises(ValidationError):
        QuoteRequestCreate.model_validate(_request_payload("INSTAGRAM"))


def test_dashboard_displays_distinct_google_and_website_sources() -> None:
    assert _display_source("WEBSITE") == "Website"
    assert _display_source("GOOGLE") == "Google Search"


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
