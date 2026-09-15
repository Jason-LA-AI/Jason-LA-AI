"""Tests for structured airport quote estimates."""

from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.schemas.quote_estimate import QuoteEstimateCreate
from app.services.location_normalizer import normalize_location
from app.services.quote_estimate_service import (
    ROUTE_MILEAGE_PRICING_SOURCE,
    create_quote_estimate,
    customer_numeric_fare_is_available,
)
from app.services.route_pricing import RouteMileage, RouteMileageUnavailable


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


@pytest.fixture(autouse=True)
def successful_road_mileage(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep quote tests offline while exercising the mapped-price path."""

    monkeypatch.setattr(
        "app.services.quote_estimate_service.get_round_trip_mileage",
        lambda *_: RouteMileage(
            total_miles=Decimal("100"), distance_meters=160934
        ),
    )


def test_zip_91789_normalizes_to_walnut() -> None:
    location = normalize_location("91789")

    assert location["normalized_city"] == "Walnut"
    assert location["postal_code"] == "91789"
    assert location["pricing_zone"] == "WALNUT"


def test_zip_only_location_receives_a_mileage_price() -> None:
    session = _session()

    response = create_quote_estimate(_request(), session)

    assert response.status.value == "ESTIMATED"
    assert response.route_summary == "Walnut → ONT"
    assert response.estimated_min_amount == 100
    assert response.estimated_max_amount == 150
    estimate = session.add.call_args.args[0]
    assert estimate.flight_number == "UA123"
    assert estimate.estimated_min_amount == 100
    assert estimate.estimated_max_amount == 150
    assert estimate.pricing_source == ROUTE_MILEAGE_PRICING_SOURCE


def test_lax_to_zip_only_receives_a_mileage_price() -> None:
    session = _session()

    response = create_quote_estimate(
        _request(
            service_type="AIRPORT_PICKUP",
            airport_code="LAX",
            location_input="90045",
        ),
        session,
    )

    assert response.status.value == "ESTIMATED"
    assert response.route_summary == "LAX → 90045"
    assert response.estimated_min_amount == 100
    assert response.estimated_max_amount == 150
    estimate = session.add.call_args.args[0]
    assert estimate.estimated_min_amount == 100
    assert estimate.estimated_max_amount == 150


def test_street_address_receives_a_mileage_price_and_preserves_route() -> None:
    session = _session()
    response = create_quote_estimate(
        _request(location_input="123 Main Street, Los Angeles"),
        session,
    )

    assert response.status.value == "ESTIMATED"
    assert response.estimated_min_amount == 100
    assert response.estimated_max_amount == 150
    assert response.route_summary == "123 Main Street, Los Angeles → ONT"
    estimate = session.add.call_args.args[0]
    assert estimate.estimated_min_amount == 100
    assert estimate.estimated_max_amount == 150


def test_hotel_receives_a_mileage_price_and_preserves_route() -> None:
    session = _session()
    response = create_quote_estimate(
        _request(location_input="Hyatt Regency LAX"),
        session,
    )

    assert response.status.value == "ESTIMATED"
    assert response.estimated_min_amount == 100
    assert response.estimated_max_amount == 150
    assert response.route_summary == "Hyatt Regency LAX → ONT"
    assert session.add.call_args.args[0].suggested_amount == 125


def test_unavailable_road_mileage_requires_manual_fare_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(*_: object) -> RouteMileage:
        raise RouteMileageUnavailable("not configured")

    monkeypatch.setattr(
        "app.services.quote_estimate_service.get_round_trip_mileage", unavailable
    )

    response = create_quote_estimate(_request(), _session())

    assert response.status.value == "MANUAL_REVIEW_REQUIRED"
    assert response.estimated_min_amount == 100
    assert response.estimated_max_amount == 140
    assert "ROUTE_MILEAGE_UNAVAILABLE" in response.risk_flags


@pytest.mark.parametrize(
    "location",
    ["Rowland Heights", "Walnut", "Arcadia", "Ontario", "Rancho Cucamonga"],
)
def test_city_only_routes_receive_a_mileage_price(location: str) -> None:
    response = create_quote_estimate(
        _request(location_input=location, service_type="AIRPORT_PICKUP"),
        _session(),
    )

    assert response.status.value == "ESTIMATED"
    assert response.estimated_min_amount == 100
    assert response.estimated_max_amount == 150


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
            "location_input": "123 Main Street, Los Angeles",
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
    assert body["estimated_min_amount"] == "100"
    assert body["estimated_max_amount"] == "150"


def test_only_road_mileage_pricing_can_show_customer_fare() -> None:
    assert customer_numeric_fare_is_available(
        pricing_source=ROUTE_MILEAGE_PRICING_SOURCE,
        risk_flags=[],
    )
    assert not customer_numeric_fare_is_available(
        pricing_source=ROUTE_MILEAGE_PRICING_SOURCE,
        risk_flags=["ROUTE_MILEAGE_UNAVAILABLE"],
    )
    assert not customer_numeric_fare_is_available(
        pricing_source="development_mock",
        risk_flags=[],
    )


def test_api_paths_are_not_canonical_redirected(client) -> None:
    """The public-page canonical middleware must never capture API routes."""

    response = client.post("/api/v1/quote-estimates/", json={}, follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "http://testserver/api/v1/quote-estimates"
