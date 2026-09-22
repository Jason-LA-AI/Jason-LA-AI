"""Permanent regression matrix for canonical city input variants."""

from datetime import date, time
from decimal import Decimal
from uuid import uuid4

import pytest

from app.schemas.quote_estimate import QuoteEstimateCreate
from app.services.city_mileage_archive import ARCHIVE_PATH
from app.services.quote_estimate_service import MAX_AUTO_QUOTE_CLOSED_LOOP_MILES, create_quote_estimate


class _Session:
    def add(self, value): self.value = value
    def flush(self):
        if self.value.id is None: self.value.id = uuid4()
    def refresh(self, value): pass
    def commit(self): pass
    def rollback(self): pass


def _numeric_cases():
    import json
    profiles = json.loads(ARCHIVE_PATH.read_text(encoding="utf-8"))["profiles"]
    approval_scoped = {"Las Vegas", "San Francisco", "San Diego", "Santa Barbara"}
    cases = []
    for profile in profiles.values():
        city = profile["destination"]
        state = "NV" if city == "Las Vegas" else "CA"
        for airport in ("LAX", "ONT"):
            for service in ("AIRPORT_PICKUP", "AIRPORT_DROPOFF"):
                airport_data = profile.get("airports", {}).get(airport)
                if not profile.get("route_available", True) or not airport_data:
                    continue
                direction = "pickup" if service == "AIRPORT_PICKUP" else "dropoff"
                legs = airport_data[f"airport_{direction}_legs_miles"]
                if any(not leg for leg in legs) and city != "Rowland Heights":
                    continue
                if airport_data[f"airport_{direction}_miles"] > float(MAX_AUTO_QUOTE_CLOSED_LOOP_MILES):
                    continue
                if city in approval_scoped and (airport, service) != ("LAX", "AIRPORT_PICKUP"):
                    continue
                cases.append((city, state, airport, service))
    return cases


@pytest.mark.parametrize(("city", "state", "airport", "service"), _numeric_cases())
def test_numeric_routes_survive_safe_city_state_variants(city, state, airport, service):
    variants = (city, city.lower(), f"{city}, {state}", f"{city} {state}", f"{city}, {'Nevada' if state == 'NV' else 'California'}")
    for location in variants:
        request = QuoteEstimateCreate(
            service_type=service, airport_code=airport, service_date=date.today(), service_time=time(12),
            location_input=location, passenger_count="2", large_luggage_count="1",
            child_seat_required=False, oversized_items=False,
        )
        response = create_quote_estimate(request, _Session())
        assert response.estimated_min_amount is not None, (city, airport, service, location)
        assert response.estimated_max_amount is not None, (city, airport, service, location)
