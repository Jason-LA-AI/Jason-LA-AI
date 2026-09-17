"""Tests for structured airport quote estimates."""

from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.schemas.quote_estimate import QuoteEstimateCreate
from app.schemas.quote_request import QuoteRequestCreate
from app.models.outbox_event import OutboxEvent
from app.models.quote import Quote
from app.models.quote_estimate import QuoteEstimate
from app.services.location_normalizer import normalize_location
from app.services.quote_estimate_service import (
    ROUTE_MILEAGE_PRICING_SOURCE,
    create_quote_estimate,
    customer_numeric_fare_is_available,
)
from app.services.quote_request_service import (
    _pricing_recommendation_text,
    process_quote_request,
)
from app.services.route_pricing import RouteMileageUnavailable
from app.api.dashboard import _pricing_details


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


class _RequestFlowSession:
    """Small in-memory Session double for the complete request orchestration."""

    def __init__(self) -> None:
        self.added: list[object] = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, value: object) -> None:
        if getattr(value, "id", None) is None:
            value.id = uuid4()
        self.added.append(value)

    def flush(self) -> None:
        pass

    def refresh(self, value: object) -> None:
        if getattr(value, "id", None) is None:
            value.id = uuid4()

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def scalar(self, *_: object) -> None:
        return None

    def get(self, model: object, identifier: object) -> QuoteEstimate | None:
        if model is not QuoteEstimate:
            return None
        return next(
            (
                value
                for value in self.added
                if isinstance(value, QuoteEstimate) and value.id == identifier
            ),
            None,
        )


def _request_confirmation(estimate_id: object) -> QuoteRequestCreate:
    return QuoteRequestCreate.model_validate(
        {
            "estimate_id": estimate_id,
            "customer_name": "Local Validation Customer",
            "email": "local-validation@example.com",
            "estimate_acceptance": True,
        }
    )


def test_zip_only_location_is_not_mapped_to_a_city_center() -> None:
    location = normalize_location("91789")

    assert location["normalized_city"] is None
    assert location["postal_code"] == "91789"
    assert location["pricing_zone"] == "UNKNOWN_LOCATION"


def test_zip_only_location_requires_fare_review() -> None:
    session = _session()

    response = create_quote_estimate(_request(), session)

    assert response.status.value == "MANUAL_REVIEW_REQUIRED"
    assert response.route_summary == "91789 → ONT"
    assert response.estimated_min_amount is None
    assert response.estimated_max_amount is None
    estimate = session.add.call_args.args[0]
    assert estimate.flight_number == "UA123"
    assert estimate.estimated_min_amount is None
    assert estimate.estimated_max_amount is None
    assert estimate.pricing_source == "route_mileage_unavailable"
    assert "UNKNOWN_LOCATION" in response.risk_flags


def test_unknown_zip_requires_fare_review() -> None:
    session = _session()

    response = create_quote_estimate(
        _request(
            service_type="AIRPORT_PICKUP",
            airport_code="LAX",
            location_input="90045",
        ),
        session,
    )

    assert response.status.value == "MANUAL_REVIEW_REQUIRED"
    assert response.route_summary == "LAX → 90045"
    assert response.estimated_min_amount is None
    assert response.estimated_max_amount is None
    assert "UNKNOWN_LOCATION" in response.risk_flags
    assert "ROUTE_MILEAGE_UNAVAILABLE" in response.risk_flags
    estimate = session.add.call_args.args[0]
    assert estimate.estimated_min_amount is None
    assert estimate.estimated_max_amount is None


@pytest.mark.parametrize("location", ["91748", "91789", "90045"])
def test_all_zip_only_inputs_require_fare_review(location: str) -> None:
    response = create_quote_estimate(_request(location_input=location), _session())

    assert response.status.value == "MANUAL_REVIEW_REQUIRED"
    assert response.estimated_min_amount is None
    assert response.estimated_max_amount is None


@pytest.mark.parametrize(
    "location",
    [
        "Rowland Heights",
        "Walnut",
        "Chino",
        "Riverside",
        "Moreno Valley",
        "San Bernardino",
        "San Bernadino",
        "sen bernardino",
        "Rancho Cucamonga",
        "rencho cucamonga",
        "DTLA",
        "Downtown LA",
        "Downtown Los Angeles",
        "Brea",
        "La Habra",
        "Laguna Hills",
        "Mission Viejo",
        "Tustin",
        "Orange",
        "Disneyland",
        "UCLA",
        "USC",
        "UC Riverside",
    ],
)
def test_verified_city_alias_and_landmark_inputs_receive_numeric_estimates(
    location: str,
) -> None:
    response = create_quote_estimate(_request(location_input=location), _session())

    assert response.status.value == "ESTIMATED"
    assert response.estimated_min_amount is not None
    assert response.estimated_max_amount is not None
    assert response.location_suggestion is None


@pytest.mark.parametrize(
    ("location", "canonical", "display_name"),
    [
        ("Downtown", "Downtown Los Angeles", "Downtown Los Angeles (DTLA)"),
        ("Disney", "Disneyland", "Disneyland"),
    ],
)
def test_safe_suggestion_requires_explicit_canonical_reestimate(
    location: str,
    canonical: str,
    display_name: str,
) -> None:
    initial = create_quote_estimate(_request(location_input=location), _session())

    assert initial.status.value == "MANUAL_REVIEW_REQUIRED"
    assert initial.estimated_min_amount is None
    assert initial.estimated_max_amount is None
    assert initial.location_suggestion is not None
    assert initial.location_suggestion.canonical_location == canonical
    assert initial.location_suggestion.display_name == display_name

    confirmed = create_quote_estimate(_request(location_input=canonical), _session())
    assert confirmed.status.value == "ESTIMATED"
    assert confirmed.estimated_min_amount is not None
    assert confirmed.estimated_max_amount is not None


@pytest.mark.parametrize(
    "location",
    [
        "123 Main Street, Riverside, CA 92501",
        "123 Main Street, Rowland Heights, CA 91748",
        "random nonexistent location",
        "Thousand Oaks",
        "Oxnard",
        "Ventura",
        "Santa Barbara",
        "San Diego",
        "San Jose",
        "Joshua Tree",
    ],
)
def test_unverified_addresses_and_unknown_places_require_fare_review(location: str) -> None:
    response = create_quote_estimate(_request(location_input=location), _session())

    assert response.status.value == "MANUAL_REVIEW_REQUIRED"
    assert response.estimated_min_amount is None
    assert response.estimated_max_amount is None
    assert response.location_suggestion is None


def test_unverified_street_address_requires_fare_review_and_preserves_route() -> None:
    session = _session()
    response = create_quote_estimate(
        _request(location_input="123 Main Street, Los Angeles"),
        session,
    )

    assert response.status.value == "MANUAL_REVIEW_REQUIRED"
    assert response.estimated_min_amount is None
    assert response.estimated_max_amount is None
    assert "UNKNOWN_LOCATION" in response.risk_flags
    assert response.route_summary == "123 Main Street, Los Angeles → ONT"
    estimate = session.add.call_args.args[0]
    assert estimate.estimated_min_amount is None
    assert estimate.estimated_max_amount is None


def test_unverified_hotel_requires_fare_review_and_preserves_route() -> None:
    session = _session()
    response = create_quote_estimate(
        _request(location_input="Hyatt Regency LAX"),
        session,
    )

    assert response.status.value == "MANUAL_REVIEW_REQUIRED"
    assert response.estimated_min_amount is None
    assert response.estimated_max_amount is None
    assert response.route_summary == "Hyatt Regency LAX → ONT"
    assert session.add.call_args.args[0].suggested_amount is None


def test_unavailable_road_mileage_requires_manual_fare_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(*_: object) -> object:
        raise RouteMileageUnavailable("not configured")

    monkeypatch.setattr(
        "app.services.quote_estimate_service.get_archived_round_trip_mileage", unavailable
    )

    response = create_quote_estimate(_request(), _session())

    assert response.status.value == "MANUAL_REVIEW_REQUIRED"
    assert response.estimated_min_amount is None
    assert response.estimated_max_amount is None
    assert "ROUTE_MILEAGE_UNAVAILABLE" in response.risk_flags
    assert response.notices == ["Jason will review the exact route and confirm the fare."]


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
    assert response.estimated_min_amount is not None
    assert response.estimated_max_amount is not None


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
            "service_date": "2026-09-17",
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
        "location_suggestion",
        "valid_until",
    }
    assert body["status"] == "MANUAL_REVIEW_REQUIRED"
    assert body["estimated_min_amount"] is None
    assert body["estimated_max_amount"] is None
    assert body["location_suggestion"] is None


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
    assert not customer_numeric_fare_is_available(
        pricing_source="google_routes_mileage_v1",
        risk_flags=[],
    )
    assert not customer_numeric_fare_is_available(
        pricing_source=ROUTE_MILEAGE_PRICING_SOURCE,
        risk_flags=["LARGE_LUGGAGE_4_PLUS"],
    )


def test_manual_vehicle_review_withholds_customer_numeric_estimate() -> None:
    response = create_quote_estimate(
        _request(
            service_type="AIRPORT_PICKUP",
            airport_code="LAX",
            location_input="Chino",
            large_luggage_count="4+",
        ),
        _session(),
    )

    assert response.status.value == "MANUAL_REVIEW_REQUIRED"
    assert response.estimated_min_amount is None
    assert response.estimated_max_amount is None
    assert response.notices == ["Jason will review the exact route and confirm the fare."]


@pytest.mark.parametrize(
    ("location", "expects_customer_fare"),
    [
        ("Chino", True),
        ("Las Vegas", True),
        ("San Francisco", True),
        ("123 Main Street, Riverside, CA 92501", False),
    ],
)
def test_quote_request_submission_handles_numeric_and_manual_review_estimates(
    location: str,
    expects_customer_fare: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Confirmation submission persists every estimate type without null errors."""

    session = _RequestFlowSession()
    monkeypatch.setattr(
        "app.services.quote_request_service.send_approval_notification",
        lambda *_: None,
    )
    estimate_response = create_quote_estimate(
        _request(
            service_type="AIRPORT_PICKUP",
            airport_code="LAX",
            location_input=location,
        ),
        session,
    )
    estimate = next(value for value in session.added if isinstance(value, QuoteEstimate))

    result = process_quote_request(session, _request_confirmation(estimate_response.estimate_id))
    quote = next(value for value in session.added if isinstance(value, Quote))
    outbox = next(value for value in session.added if isinstance(value, OutboxEvent))

    assert result.estimate_id == estimate.id
    assert session.rollbacks == 0
    assert quote.suggested_amount is not None if expects_customer_fare else quote.suggested_amount is None
    assert outbox.payload["suggested_amount"] is not None if expects_customer_fare else outbox.payload["suggested_amount"] is None

    if location in {"Las Vegas", "San Francisco"}:
        assert estimate.pricing_source == "approved_long_distance_range_v1"
        assert estimate.pricing_factors["approved_long_distance_range"] is True
        assert "APPROVED LONG-DISTANCE RANGE" in _pricing_recommendation_text(estimate)
        dashboard_details = _pricing_details(quote)
        assert "APPROVED LONG-DISTANCE RANGE" in dashboard_details
        assert "Closed-loop mileage:" in dashboard_details
        assert "Approved customer range:" in dashboard_details


def test_api_paths_are_not_canonical_redirected(client) -> None:
    """The public-page canonical middleware must never capture API routes."""

    response = client.post("/api/v1/quote-estimates/", json={}, follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "http://testserver/api/v1/quote-estimates"
