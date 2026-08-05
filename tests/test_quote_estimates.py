"""Tests for structured airport quote estimates."""

from datetime import datetime
from unittest.mock import MagicMock
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.schemas.quote_estimate import QuoteEstimateCreate
from app.services.location_normalizer import normalize_location
from app.services.quote_estimate_service import create_quote_estimate


def _request(**overrides: object) -> QuoteEstimateCreate:
    values: dict[str, object] = {
        "service_type": "AIRPORT_DROPOFF",
        "airport_code": "ONT",
        "service_date": datetime.now(ZoneInfo("America/Los_Angeles")).date(),
        "service_time": "08:30",
        "flight_number": "UA123",
        "location_input": "91789",
        "passenger_count": "2",
        "large_luggage_count": "2",
        "child_seat_required": False,
        "oversized_items": False,
    }
    values.update(overrides)
    return QuoteEstimateCreate.model_validate(values)


def _session() -> MagicMock:
    session = MagicMock()

    def refresh(estimate: object) -> None:
        estimate.id = uuid4()

    session.refresh.side_effect = refresh
    return session


def test_zip_91789_normalizes_to_walnut() -> None:
    location = normalize_location("91789")

    assert location["normalized_city"] == "Walnut"
    assert location["postal_code"] == "91789"
    assert location["pricing_zone"] == "WALNUT"


def test_ont_dropoff_from_91789_returns_estimated_range() -> None:
    session = _session()

    response = create_quote_estimate(_request(), session)

    assert response.status.value == "ESTIMATED"
    assert response.route_summary == "Walnut → ONT"
    assert response.estimated_min_amount == 100
    assert response.estimated_max_amount == 140
    estimate = session.add.call_args.args[0]
    assert estimate.flight_number == "UA123"


def test_manual_review_keeps_price_when_location_is_free_text() -> None:
    response = create_quote_estimate(
        _request(location_input="Customer-provided pickup location"),
        _session(),
    )

    assert response.status.value == "MANUAL_REVIEW_REQUIRED"
    assert response.estimated_min_amount == 100
    assert response.estimated_max_amount == 140


@pytest.mark.parametrize(
    "location",
    ["San Diego", "San Jose, CA", "Santa Barbara", "Las Vegas, NV"],
)
def test_long_distance_routes_require_confirmation_without_price(location: str) -> None:
    response = create_quote_estimate(
        _request(location_input=location, service_type="AIRPORT_PICKUP"),
        _session(),
    )

    assert response.status.value == "MANUAL_REVIEW_REQUIRED"
    assert response.estimated_min_amount is None
    assert response.estimated_max_amount is None
    assert "LONG_DISTANCE_ROUTE" in response.risk_flags


@pytest.mark.parametrize(
    "location",
    ["Rowland Heights", "Walnut", "Arcadia", "Ontario", "Rancho Cucamonga"],
)
def test_known_local_routes_keep_automatic_estimates(location: str) -> None:
    response = create_quote_estimate(
        _request(location_input=location, service_type="AIRPORT_PICKUP"),
        _session(),
    )

    assert response.status.value == "ESTIMATED"
    assert response.estimated_min_amount == 100
    assert response.estimated_max_amount == 140
