from decimal import Decimal

import pytest

from app.services.city_mileage_archive import lookup_archived_mileage


def test_walnut_uses_the_precomputed_ont_pickup_loop() -> None:
    result = lookup_archived_mileage(
        service_type="AIRPORT_PICKUP", airport_code="ONT", location="Walnut"
    )

    assert result is not None
    assert result.destination == "Walnut"
    assert result.total_miles == Decimal("46.7")


def test_ucsd_alias_uses_the_requested_special_destination() -> None:
    result = lookup_archived_mileage(
        service_type="AIRPORT_DROPOFF", airport_code="LAX", location="UCSD"
    )

    assert result is not None
    assert result.destination == "UC San Diego"
    assert result.total_miles == Decimal("247.0")


def test_rowland_heights_uses_the_precomputed_lax_loop() -> None:
    result = lookup_archived_mileage(
        service_type="AIRPORT_PICKUP", airport_code="LAX", location="Rowland Heights"
    )

    assert result is not None
    assert result.destination == "Rowland Heights"
    assert result.total_miles == Decimal("76.2")


def test_avalon_has_no_drivable_archive_route() -> None:
    assert lookup_archived_mileage(
        service_type="AIRPORT_PICKUP", airport_code="LAX", location="Avalon"
    ) is None


@pytest.mark.parametrize(
    ("location", "airport", "service_type", "expected_miles"),
    [
        ("Brea", "LAX", "AIRPORT_PICKUP", "77.7"),
        ("Brea", "ONT", "AIRPORT_DROPOFF", "52.8"),
        ("La Habra", "LAX", "AIRPORT_PICKUP", "71.7"),
        ("La Habra", "ONT", "AIRPORT_DROPOFF", "53.6"),
        ("Laguna Hills", "LAX", "AIRPORT_PICKUP", "125.9"),
        ("Laguna Hills", "ONT", "AIRPORT_DROPOFF", "98.8"),
        ("Mission Viejo", "LAX", "AIRPORT_PICKUP", "128.0"),
        ("Mission Viejo", "ONT", "AIRPORT_DROPOFF", "100.9"),
        ("Tustin", "LAX", "AIRPORT_PICKUP", "101.7"),
        ("Tustin", "ONT", "AIRPORT_DROPOFF", "82.6"),
        ("Orange", "LAX", "AIRPORT_PICKUP", "91.9"),
        ("Orange", "ONT", "AIRPORT_DROPOFF", "72.6"),
    ],
)
def test_batch_2a_profiles_have_verified_directional_mileage(
    location: str, airport: str, service_type: str, expected_miles: str
) -> None:
    result = lookup_archived_mileage(
        service_type=service_type, airport_code=airport, location=location
    )

    assert result is not None
    assert result.destination == location
    assert result.total_miles == Decimal(expected_miles)


@pytest.mark.parametrize("location", ["Thousand Oaks", "Oxnard", "Ventura", "Santa Barbara"])
def test_withheld_long_distance_destinations_remain_unavailable(location: str) -> None:
    assert lookup_archived_mileage(
        service_type="AIRPORT_PICKUP", airport_code="LAX", location=location
    ) is None


@pytest.mark.parametrize("airport", ["SNA", "BUR", "LGB"])
def test_unverified_airport_axes_cannot_use_lax_or_ont_mileage(airport: str) -> None:
    assert lookup_archived_mileage(
        service_type="AIRPORT_PICKUP", airport_code=airport, location="Chino"
    ) is None
