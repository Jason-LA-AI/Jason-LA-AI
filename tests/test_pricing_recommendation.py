"""Internal pricing recommendation display tests."""

from datetime import datetime, timezone
from decimal import Decimal

from app.api.dashboard import _build_inquiry_view
from app.models.customer import Customer
from app.models.lead import Lead
from app.models.notification import Notification
from app.models.quote import Quote
from app.services.quote_request_service import _pricing_recommendation_text
from app.services.telegram_adapter import _render_quote_request_review


def _lead_and_customer() -> tuple[Lead, Customer]:
    customer = Customer(
        display_name="Pricing Customer",
        primary_contact="6265550100",
        primary_contact_type="phone",
        source="WEBSITE",
    )
    lead = Lead(
        source="WEBSITE",
        status="PENDING_JASON",
        received_at=datetime.now(timezone.utc),
        intake_method="STRUCTURED_QUOTE_V2",
        route_summary="LAX → Rowland Heights",
    )
    return lead, customer


def _notification_payload(**pricing: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "approval_id": "approval",
        "order_id": "order",
        "quote_id": "quote",
        "estimate_id": "estimate",
        "service_type": "AIRPORT_PICKUP",
        "source": "WEBSITE",
        "route_summary": "LAX → Rowland Heights",
    }
    payload.update(pricing)
    return payload


def test_dashboard_displays_quote_pricing_recommendation() -> None:
    lead, customer = _lead_and_customer()
    quote = Quote(
        currency_code="USD",
        suggested_min_amount=Decimal("130.00"),
        suggested_max_amount=Decimal("150.00"),
        suggested_amount=Decimal("140.00"),
        pricing_source="development_mock",
    )

    view = _build_inquiry_view(lead, customer, quote)

    assert view["suggested_price"] == "USD 140.00"
    assert view["price_range"] == "USD 130.00–150.00"
    assert view["pricing_source"] == "development_mock"


def test_dashboard_manual_lead_without_quote_is_not_estimated() -> None:
    lead, customer = _lead_and_customer()

    view = _build_inquiry_view(lead, customer, None)

    assert view["suggested_price"] == "Not estimated"
    assert view["price_range"] == "Not estimated"
    assert view["pricing_source"] == "Not estimated"


def test_telegram_displays_pricing_recommendation_and_source() -> None:
    notification = Notification(
        channel="TELEGRAM",
        status="PENDING",
        template_key="QUOTE_REQUEST_REVIEW",
        payload=_notification_payload(
            suggested_amount="140.00",
            estimated_min_amount="130.00",
            estimated_max_amount="150.00",
            currency_code="USD",
            pricing_source="development_mock",
            pricing_status="ESTIMATED",
        ),
        attempt_count=0,
    )

    message = _render_quote_request_review(notification)

    assert "Pricing Recommendation:" in message
    assert "Suggested Amount: 140.00" in message
    assert "Range: 130.00 - 150.00" in message
    assert "Currency: USD" in message
    assert "Pricing Source: development_mock" in message
    assert "Pricing Status: ESTIMATED" in message
    assert "AI Price" not in message


def test_telegram_without_prices_requires_manual_review() -> None:
    notification = Notification(
        channel="TELEGRAM",
        status="PENDING",
        template_key="QUOTE_REQUEST_REVIEW",
        payload=_notification_payload(
            pricing_source="development_mock",
            pricing_status="MANUAL_REVIEW_REQUIRED",
        ),
        attempt_count=0,
    )

    message = _render_quote_request_review(notification)

    assert "Manual Review Required" in message
    assert "Pricing Source: development_mock" in message


def test_direct_approval_notification_uses_persisted_estimate_values() -> None:
    estimate = type(
        "Estimate",
        (),
        {
            "suggested_amount": Decimal("140.00"),
            "estimated_min_amount": Decimal("130.00"),
            "estimated_max_amount": Decimal("150.00"),
            "currency_code": "USD",
            "pricing_source": "development_mock",
            "status": "ESTIMATED",
        },
    )()

    message = _pricing_recommendation_text(estimate)

    assert "Suggested Amount: 140.00" in message
    assert "Range: 130.00 - 150.00" in message
    assert "Pricing Source: development_mock" in message
