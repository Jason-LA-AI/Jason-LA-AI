"""Safety regressions for quote contact matching and dashboard labels."""

from datetime import datetime, timezone
from unittest.mock import Mock

from app.api.dashboard import _build_inquiry_view
from app.models.customer import Customer
from app.models.lead import Lead
from app.services.customer_service import create_or_match_customer


def _customer(*, contact: str, contact_type: str, method: str | None = None) -> Customer:
    return Customer(
        display_name="Jason",
        primary_contact=contact,
        primary_contact_type=contact_type,
        preferred_contact_method=method,
        source="UNKNOWN",
    )


def _dashboard_contact(customer: Customer) -> str:
    lead = Lead(
        source="UNKNOWN",
        customer=customer,
        received_at=datetime.now(timezone.utc),
    )
    return _build_inquiry_view(lead, customer)["contact"]


def test_dashboard_labels_line_and_wechat_contacts_explicitly() -> None:
    assert _dashboard_contact(_customer(contact="line123", contact_type="other", method="LINE")) == "LINE: line123"
    assert _dashboard_contact(_customer(contact="wechat123", contact_type="wechat", method="WECHAT")) == "WeChat: wechat123"


def test_dashboard_keeps_phone_and_email_display_unchanged() -> None:
    assert _dashboard_contact(_customer(contact="6265550100", contact_type="phone", method="SMS")) == "6265550100"
    assert _dashboard_contact(_customer(contact="jason@example.com", contact_type="email", method="EMAIL")) == "jason@example.com"


def test_repeated_wechat_exact_contact_reuses_existing_customer() -> None:
    existing = _customer(contact="abc123", contact_type="wechat", method="WECHAT")
    db = Mock(); db.scalar.return_value = existing

    result = create_or_match_customer(db, customer_name="A", phone=None, email=None, wechat_id="abc123", line_id=None, preferred_contact_method="WECHAT", source="UNKNOWN")

    assert result is existing
    db.add.assert_not_called()


def test_repeated_line_exact_contact_reuses_existing_customer() -> None:
    existing = _customer(contact="line123", contact_type="other", method="LINE")
    db = Mock(); db.scalar.return_value = existing

    result = create_or_match_customer(db, customer_name="A", phone=None, email=None, wechat_id=None, line_id="line123", preferred_contact_method="LINE", source="UNKNOWN")

    assert result is existing
    db.add.assert_not_called()


def test_same_name_with_different_contact_never_auto_merges() -> None:
    db = Mock(); db.scalar.return_value = None

    result = create_or_match_customer(db, customer_name="Jason", phone=None, email=None, wechat_id="new-id", line_id=None, preferred_contact_method="WECHAT", source="UNKNOWN")

    assert result.display_name == "Jason"
    assert result.primary_contact == "new-id"
    db.add.assert_called_once_with(result)


def test_phone_only_customer_and_wechat_only_request_do_not_unsafe_merge() -> None:
    db = Mock(); db.scalar.return_value = None

    result = create_or_match_customer(db, customer_name="Same Name", phone=None, email=None, wechat_id="abc123", line_id=None, preferred_contact_method="WECHAT", source="UNKNOWN")

    assert result.primary_contact == "abc123"
    assert result.primary_contact_type == "wechat"
    db.add.assert_called_once_with(result)
