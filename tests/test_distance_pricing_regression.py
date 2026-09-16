"""Regression tests for the closed-loop road-mileage pricing policy."""

from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.schemas.quote_estimate import QuoteEstimateCreate
from app.services.city_mileage_archive import lookup_archived_mileage, supported_destinations
from app.services.location_normalizer import UNKNOWN_LOCATION, normalize_location, suggest_location
from app.services.quote_estimate_service import (
    create_quote_estimate,
    customer_numeric_fare_is_available,
)
from app.services.route_pricing import get_archived_round_trip_mileage, price_range_for_miles
from app.services.quote_request_service import _pricing_recommendation_text


REQUIRED_DESTINATIONS = {
    "Los Angeles", "Downtown Los Angeles", "Koreatown", "West Hollywood", "Hollywood",
    "Beverly Hills", "Santa Monica", "Venice", "Westchester", "Inglewood", "Torrance",
    "Pasadena", "Arcadia", "San Marino", "Alhambra", "Monterey Park", "Montebello",
    "El Monte", "West Covina", "Covina", "Walnut", "Diamond Bar", "Rowland Heights",
    "Hacienda Heights", "Whittier", "La Puente", "Pomona", "Claremont", "Glendora",
    "Azusa", "La Verne", "Chino", "Chino Hills", "Ontario", "Rancho Cucamonga",
    "Fontana", "Riverside", "Moreno Valley", "San Bernardino", "Eastvale", "Corona",
    "Redlands", "Upland", "Anaheim", "Disneyland", "Fullerton", "Buena Park",
    "Garden Grove", "Irvine", "Costa Mesa", "Newport Beach", "Laguna Beach", "Lake Forest",
    "Aliso Viejo", "Santa Ana", "UCLA", "USC", "UC Irvine", "UC Riverside",
    "Cal Lutheran", "Santa Monica College",
}


def _request(
    location: str = "Chino",
    service_type: str = "AIRPORT_PICKUP",
    airport_code: str = "LAX",
) -> QuoteEstimateCreate:
    return QuoteEstimateCreate.model_validate(
        {
            "service_type": service_type,
            "airport_code": airport_code,
            "service_date": datetime.now(ZoneInfo("America/Los_Angeles")).date(),
            "service_time": "08:30",
            "location_input": location,
            "passenger_count": "2",
            "large_luggage_count": "1",
            "child_seat_required": False,
            "oversized_items": False,
        }
    )


def _session() -> MagicMock:
    session = MagicMock()
    session.refresh.side_effect = lambda estimate: setattr(estimate, "id", uuid4())
    return session


def test_full_requested_destination_matrix_has_lax_and_ont_road_legs() -> None:
    destinations = set(supported_destinations().values())
    assert REQUIRED_DESTINATIONS <= destinations

    for destination in destinations:
        for airport in ("LAX", "ONT"):
            mileage = lookup_archived_mileage(
                service_type="AIRPORT_PICKUP", airport_code=airport, location=destination
            )
            if destination == "Avalon":
                assert mileage is None
                continue
            assert mileage is not None
            assert all(
                    value is not None and value >= 0
                for value in (mileage.leg_1_miles, mileage.leg_2_miles, mileage.leg_3_miles)
            )
            assert mileage.total_miles > 0


@pytest.mark.parametrize(
    ("raw", "canonical"),
    [
        ("San Bernardino", "San Bernardino"),
        ("Rancho Cucamonga", "Rancho Cucamonga"),
        ("Moreno Valley", "Moreno Valley"),
        ("Rowland Heights", "Rowland Heights"),
        ("Koreatown", "Koreatown"),
    ],
)
def test_canonical_archive_locations_normalize_directly(raw: str, canonical: str) -> None:
    assert normalize_location(raw)["normalized_city"] == canonical


@pytest.mark.parametrize(
    ("raw", "canonical"),
    [
        ("DTLA", "Downtown Los Angeles"),
        ("Downtown LA", "Downtown Los Angeles"),
        ("Downtown Los Angeles", "Downtown Los Angeles"),
        ("San Bernardino", "San Bernardino"),
        ("San Bernadino", "San Bernardino"),
        ("sen bernardino", "San Bernardino"),
        ("Rancho Cucamonga", "Rancho Cucamonga"),
        ("rencho cucamonga", "Rancho Cucamonga"),
    ],
)
def test_explicit_safe_aliases_normalize_directly(
    raw: str, canonical: str
) -> None:
    normalized = normalize_location(raw)

    assert normalized["normalized_city"] == canonical
    assert suggest_location(raw) is None


@pytest.mark.parametrize(
    ("raw", "canonical"),
    [
        ("Downtown", "Downtown Los Angeles"),
        ("Disney", "Disneyland"),
        ("Ontario Airport", "ONT"),
        ("LA Airport", "LAX"),
    ],
)
def test_curated_ambiguous_inputs_offer_click_to_confirm_suggestions(
    raw: str, canonical: str
) -> None:
    suggestion = suggest_location(raw)

    assert normalize_location(raw)["normalized_city"] is None
    assert suggestion is not None
    assert suggestion["canonical_location"] == canonical


@pytest.mark.parametrize(
    "raw",
    ["91748", "90045", "123 Main Street, Riverside, CA 92501", "random nonexistent location"],
)
def test_zip_address_and_unknown_inputs_never_receive_city_downgrade_suggestions(raw: str) -> None:
    assert suggest_location(raw) is None


def test_invalid_city_is_not_fuzzy_matched_and_requires_review() -> None:
    location = normalize_location("San Bernar")
    assert location["pricing_zone"] == UNKNOWN_LOCATION

    response = create_quote_estimate(_request("San Bernar"), _session())
    assert response.estimated_min_amount is None
    assert response.estimated_max_amount is None
    assert "ROUTE_MILEAGE_UNAVAILABLE" in response.risk_flags


def test_lax_and_ont_closed_loops_are_distinct_and_formula_driven() -> None:
    chino_lax = get_archived_round_trip_mileage("AIRPORT_PICKUP", "LAX", "Chino")
    chino_ont = get_archived_round_trip_mileage("AIRPORT_PICKUP", "ONT", "Chino")
    riverside_lax = get_archived_round_trip_mileage("AIRPORT_PICKUP", "LAX", "Riverside")

    assert chino_lax.total_miles == Decimal("104.0")
    assert chino_ont.total_miles == Decimal("46.0")
    assert riverside_lax.total_miles == Decimal("141.5")
    assert chino_lax.total_miles != riverside_lax.total_miles
    assert price_range_for_miles(chino_lax.total_miles).maximum_amount == Decimal("145")
    assert price_range_for_miles(riverside_lax.total_miles).maximum_amount == Decimal("175")


def test_different_closed_loop_mileage_produces_different_customer_quotes() -> None:
    chino = create_quote_estimate(_request("Chino"), _session())
    riverside = create_quote_estimate(_request("Riverside"), _session())

    assert chino.estimated_min_amount == Decimal("115")
    assert chino.estimated_max_amount == Decimal("145")
    assert riverside.estimated_min_amount == Decimal("145")
    assert riverside.estimated_max_amount == Decimal("175")
    assert (chino.estimated_min_amount, chino.estimated_max_amount) != (
        riverside.estimated_min_amount,
        riverside.estimated_max_amount,
    )


def test_unavailable_mileage_never_has_a_customer_numeric_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.route_pricing import RouteMileageUnavailable

    monkeypatch.setattr(
        "app.services.quote_estimate_service.get_archived_round_trip_mileage",
        lambda *_: (_ for _ in ()).throw(RouteMileageUnavailable("provider unavailable")),
    )
    session = _session()
    response = create_quote_estimate(_request(), session)
    stored = session.add.call_args.args[0]

    assert response.estimated_min_amount is None
    assert response.estimated_max_amount is None
    assert response.notices == ["Jason will review the exact route and confirm the fare."]
    assert stored.pricing_source == "route_mileage_unavailable"
    assert stored.pricing_factors["fallback_reason"] == "provider unavailable"
    assert not customer_numeric_fare_is_available(
        pricing_source="temporary_airport_reference_v1", risk_flags=[]
    )


def test_lax_problem_destinations_use_distinct_archive_miles_and_v1_ranges() -> None:
    expected = {
        "Chino": (Decimal("104.0"), Decimal("115"), Decimal("145")),
        "Riverside": (Decimal("141.5"), Decimal("145"), Decimal("175")),
        "Moreno Valley": (Decimal("168.5"), Decimal("155"), Decimal("185")),
        "San Bernardino": (Decimal("159.7"), Decimal("150"), Decimal("180")),
    }
    actual = {}
    for destination, (miles, minimum, maximum) in expected.items():
        response = create_quote_estimate(_request(destination), _session())
        archive = get_archived_round_trip_mileage("AIRPORT_PICKUP", "LAX", destination)
        assert archive.total_miles == miles
        assert (response.estimated_min_amount, response.estimated_max_amount) == (
            minimum,
            maximum,
        )
        actual[destination] = (response.estimated_min_amount, response.estimated_max_amount)

    assert len(set(actual.values())) == len(actual)


def test_quote_estimate_uses_the_service_direction_archive_legs() -> None:
    pickup_session = _session()
    dropoff_session = _session()
    pickup = create_quote_estimate(
        _request("Chino", service_type="AIRPORT_PICKUP"), pickup_session
    )
    dropoff = create_quote_estimate(
        _request("Chino", service_type="AIRPORT_DROPOFF"), dropoff_session
    )
    pickup_factors = pickup_session.add.call_args.args[0].pricing_factors
    dropoff_factors = dropoff_session.add.call_args.args[0].pricing_factors

    assert pickup.route_summary == "LAX → Chino"
    assert dropoff.route_summary == "Chino → LAX"
    assert pickup_factors["total_road_miles"] == "104.0"
    assert dropoff_factors["total_road_miles"] == "103.5"
    assert pickup_factors["leg_1_road_miles"] == "38.7"
    assert dropoff_factors["leg_1_road_miles"] == "15.0"


@pytest.mark.parametrize(
    ("airport", "service_type", "destination", "historical_base_fare", "in_range"),
    [
        ("ONT", "AIRPORT_PICKUP", "Chino", Decimal("80"), True),
        ("ONT", "AIRPORT_PICKUP", "Disneyland", Decimal("100"), True),
        ("LAX", "AIRPORT_PICKUP", "Ontario", Decimal("130"), True),
        ("LAX", "AIRPORT_PICKUP", "Ontario", Decimal("140"), True),
        ("LAX", "AIRPORT_PICKUP", "Ontario", Decimal("150"), True),
        ("LAX", "AIRPORT_PICKUP", "Chino", Decimal("140"), True),
        ("LAX", "AIRPORT_PICKUP", "UC San Diego", Decimal("200"), True),
        # These two retained standard orders are intentionally not city-level
        # exceptions; the preliminary model truthfully misses them.
        ("LAX", "AIRPORT_DROPOFF", "Pasadena", Decimal("80"), False),
        ("LAX", "AIRPORT_DROPOFF", "Baldwin Park", Decimal("95"), False),
    ],
)
def test_real_order_regression_is_mileage_driven_without_city_exceptions(
    airport: str,
    service_type: str,
    destination: str,
    historical_base_fare: Decimal,
    in_range: bool,
) -> None:
    mileage = get_archived_round_trip_mileage(service_type, airport, destination)
    quote = price_range_for_miles(mileage.total_miles)

    assert (
        quote.minimum_amount <= historical_base_fare <= quote.maximum_amount
    ) is in_range


def test_internal_telegram_pricing_text_keeps_mileage_failure_diagnostics() -> None:
    estimate = MagicMock(
        suggested_amount=None,
        estimated_min_amount=None,
        estimated_max_amount=None,
        currency_code="USD",
        pricing_source="route_mileage_unavailable",
        status="MANUAL_REVIEW_REQUIRED",
        manual_review_reason="ROUTE_MILEAGE_UNAVAILABLE, UNKNOWN_LOCATION",
    )

    message = _pricing_recommendation_text(estimate)

    assert "Manual Review Required" in message
    assert "Pricing Source: route_mileage_unavailable" in message
    assert "Manual Review Reason: ROUTE_MILEAGE_UNAVAILABLE, UNKNOWN_LOCATION" in message
