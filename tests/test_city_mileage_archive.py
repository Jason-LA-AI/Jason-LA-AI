from decimal import Decimal

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


def test_avalon_has_no_drivable_archive_route() -> None:
    assert lookup_archived_mileage(
        service_type="AIRPORT_PICKUP", airport_code="LAX", location="Avalon"
    ) is None
