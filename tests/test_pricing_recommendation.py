"""Internal pricing recommendation display tests."""

from datetime import datetime, timezone
from decimal import Decimal

from app.api.dashboard import _build_inquiry_view
from app.models.customer import Customer
from app.models.lead import Lead
from app.models.notification import Notification
from app.models.quote import Quote
from app.services.quote_request_service import _pricing_recommendation_text, _telegram_review_text
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


def test_telegram_review_includes_wechat_contact_and_exact_trip_details() -> None:
    estimate = type(
        "Estimate",
        (),
        {
            "service_type": "AIRPORT_PICKUP",
            "airport_code": "LAX",
            "location_input": "Hyatt Regency LAX",
            "route_summary": "LAX → Hyatt Regency LAX",
            "service_date": "2026-09-15",
            "service_time": "08:30",
            "service_timezone": "America/Los_Angeles",
            "flight_number": "UA123",
            "passenger_count": 2,
            "large_suitcase_count": 3,
            "child_seat_required": "NO",
            "oversized_items_present": False,
            "suggested_amount": Decimal("140.00"),
            "estimated_min_amount": Decimal("130.00"),
            "estimated_max_amount": Decimal("150.00"),
            "currency_code": "USD",
            "pricing_source": "development_mock",
            "status": "ESTIMATED",
            "manual_review_reason": None,
        },
    )()

    message = _telegram_review_text(
        estimate=estimate,
        customer_name="Jenny",
        source="WEBSITE",
        phone=None,
        email=None,
        wechat_id="superjennygo",
        line_id=None,
        preferred_contact_method="WECHAT",
    )

    assert "Customer: Jenny" in message
    assert "Preferred Contact: WECHAT" in message
    assert "WeChat: superjennygo" in message
    assert "Phone:" not in message
    assert "LINE:" not in message
    assert "Pickup: LAX" in message
    assert "Drop-off: Hyatt Regency LAX" in message
    assert "Flight Number: UA123" in message


def test_telegram_review_includes_line_contact_without_empty_channels() -> None:
    estimate = type(
        "Estimate",
        (),
        {"service_type": "AIRPORT_DROPOFF", "airport_code": "ONT", "location_input": "UCLA Campus", "route_summary": "UCLA Campus → ONT", "service_date": "2026-09-15", "service_time": "08:30", "service_timezone": "America/Los_Angeles", "flight_number": None, "passenger_count": 1, "large_suitcase_count": 0, "child_seat_required": "NO", "oversized_items_present": False, "suggested_amount": None, "estimated_min_amount": None, "estimated_max_amount": None, "currency_code": "USD", "pricing_source": "development_mock", "status": "MANUAL_REVIEW_REQUIRED", "manual_review_reason": "UNKNOWN_LOCATION"},
    )()
    message = _telegram_review_text(estimate=estimate, customer_name="Line Customer", source="WEBSITE", phone=None, email=None, wechat_id=None, line_id="line-123", preferred_contact_method="LINE")

    assert "Preferred Contact: LINE" in message
    assert "LINE: line-123" in message
    assert "WeChat:" not in message
    assert "Manual Review Reason: UNKNOWN_LOCATION" in message


def test_telegram_review_keeps_phone_and_email_contacts() -> None:
    estimate = type(
        "Estimate",
        (),
        {"service_type": "AIRPORT_PICKUP", "airport_code": "LAX", "location_input": "Hotel June", "route_summary": "LAX → Hotel June", "service_date": "2026-09-15", "service_time": "08:30", "service_timezone": "America/Los_Angeles", "flight_number": None, "passenger_count": 1, "large_suitcase_count": 0, "child_seat_required": "NO", "oversized_items_present": False, "suggested_amount": Decimal("140"), "estimated_min_amount": Decimal("130"), "estimated_max_amount": Decimal("150"), "currency_code": "USD", "pricing_source": "development_mock", "status": "ESTIMATED", "manual_review_reason": None},
    )()
    message = _telegram_review_text(estimate=estimate, customer_name="Phone Email", source="WEBSITE", phone="6265550100", email="customer@example.com", wechat_id=None, line_id=None, preferred_contact_method="SMS")

    assert "Preferred Contact: SMS" in message
    assert "Phone: 6265550100" in message
    assert "Email: customer@example.com" in message
