"""Regression coverage for the low-friction estimate-to-request contact step."""

from uuid import uuid4

import pytest

from app.schemas.quote_request import PreferredContactMethod, QuoteRequestCreate
from app.services.quote_request_service import (
    CONTACT_METHOD_REQUIRED,
    QuoteRequestError,
    _resolve_contact,
    _source_for_request,
)


def _request(**overrides: object) -> QuoteRequestCreate:
    values: dict[str, object] = {
        "estimate_id": uuid4(),
        "customer_name": "Test Customer",
        "phone": None,
        "email": None,
        "wechat_id": None,
        "line_id": None,
        "preferred_contact_method": None,
        "estimate_acceptance": True,
    }
    values.update(overrides)
    return QuoteRequestCreate.model_validate(values)


@pytest.mark.parametrize(
    ("overrides", "expected_method"),
    [
        ({"phone": "+1 626 555 0100"}, PreferredContactMethod.SMS),
        ({"email": "customer@example.com"}, PreferredContactMethod.EMAIL),
        ({"wechat_id": "jason-trip-contact"}, PreferredContactMethod.WECHAT),
        ({"line_id": "jason-line-contact"}, PreferredContactMethod.LINE),
    ],
)
def test_each_single_contact_channel_can_complete_request_validation(
    overrides: dict[str, object],
    expected_method: PreferredContactMethod,
) -> None:
    _, _, _, _, contact_method = _resolve_contact(_request(**overrides))

    assert contact_method == expected_method


def test_source_is_optional_and_defaults_to_unknown_for_storage() -> None:
    request = _request(phone="6265550100")

    assert request.source is None
    assert _source_for_request(request) == "UNKNOWN"


def test_preferred_contact_is_optional_when_a_channel_is_present() -> None:
    request = _request(email="customer@example.com")

    assert request.preferred_contact_method is None
    assert _resolve_contact(request)[-1] == PreferredContactMethod.EMAIL


def test_no_contact_channel_is_rejected() -> None:
    with pytest.raises(QuoteRequestError, match=CONTACT_METHOD_REQUIRED):
        _resolve_contact(_request())
