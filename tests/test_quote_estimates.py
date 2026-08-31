"""Tests for structured airport quote estimates."""

from datetime import datetime
from decimal import Decimal
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


def test_quote_estimate_endpoint_returns_frontend_contract(
    client, database_session: MagicMock
) -> None:
    """A normal Step 3 quote returns JSON that the browser can render."""

    def refresh(estimate: object) -> None:
        estimate.id = uuid4()

    database_session.refresh.side_effect = refresh
    response = client.post(
        "/api/v1/quote-estimates",
        json={
            "service_type": "AIRPORT_DROPOFF",
            "airport_code": "ONT",
            "service_date": "2026-09-15",
            "service_time": "08:30",
            "service_timezone": "America/Los_Angeles",
            "flight_number": "UA123",
            "location_input": "91789",
            "passenger_count": "2",
            "large_luggage_count": "3",
            "child_seat_required": False,
            "oversized_items": False,
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert set(body) == {
        "estimate_id",
        "status",
        "route_summary",
        "estimated_min_amount",
        "estimated_max_amount",
        "currency_code",
        "vehicle_assessment",
        "requires_jason_review",
        "risk_flags",
        "notices",
        "valid_until",
    }
    assert body["status"] == "ESTIMATED"
    assert Decimal(str(body["estimated_min_amount"])) == Decimal("100")
    assert Decimal(str(body["estimated_max_amount"])) == Decimal("140")


def test_api_paths_are_not_canonical_redirected(client) -> None:
    """The public-page canonical middleware must never capture API routes."""

    response = client.post("/api/v1/quote-estimates/", json={}, follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "http://testserver/api/v1/quote-estimates"
