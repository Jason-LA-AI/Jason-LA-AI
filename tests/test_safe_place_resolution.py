"""Provider-level place verification and exact-route quote regressions."""
from copy import deepcopy
from unittest.mock import MagicMock
import pytest
from tests.test_location_input_resolution import _request, _session
from app.services.quote_estimate_service import create_quote_estimate
from app.services.location_normalizer import normalize_location


def hotel(address="1855 S Harbor Blvd, Anaheim, CA 92802, USA", place_id="hotel-1"):
    return {"types": ["lodging", "establishment", "point_of_interest"], "formatted_address": address,
            "place_id": place_id, "geometry": {"location": {"lat": 33.8, "lng": -117.9}},
            "address_components": [{"long_name": v, "short_name": "US" if t == "country" else v, "types": [t]} for t, v in
            [("street_number", "1855"), ("route", "South Harbor Boulevard"), ("locality", "Anaheim"), ("administrative_area_level_1", "California"), ("postal_code", "92802"), ("country", "United States")]]}


@pytest.fixture
def provider(monkeypatch):
    from app.services import route_pricing, place_resolution
    monkeypatch.setattr(route_pricing.settings, "google_maps_api_key", "test-key")
    get = MagicMock(return_value=MagicMock(ok=True, json=lambda: {"status": "OK", "results": [hotel()]}))
    post = MagicMock(return_value=MagicMock(ok=True, json=lambda: {"routes": [{"distanceMeters": 160934, "legs": [{"distanceMeters": 60000}, {"distanceMeters": 60000}, {"distanceMeters": 40934}]}]}))
    monkeypatch.setattr(place_resolution.requests, "get", get)
    monkeypatch.setattr(route_pricing.requests, "post", post)
    return get, post


@pytest.mark.parametrize("raw", ["Anaheim Sheraton park", "Sheraton Park Anaheim", "Hilton Anaheim", "Disneyland Hotel"])
def test_unique_hotel_gets_numeric_exact_route(raw, provider):
    get, post = provider
    session = _session()
    response = create_quote_estimate(_request(raw), session)
    assert response.resolution_type == "VERIFIED_PLACE"
    assert response.estimated_min_amount is not None
    assert response.verified_location.startswith("1855")
    record = session.add.call_args.args[0]
    assert record.pricing_source == "google_routes_exact_address_v1"
    assert record.pricing_factors["geocode_place_id"] == "hotel-1"
    assert get.call_count == post.call_count == 1
    assert post.call_args.kwargs["json"]["intermediates"][1]["location"]["latLng"]["latitude"] == 33.8
    assert normalize_location(raw)["normalized_city"] is None


def test_ambiguous_brand_returns_choices_without_route(provider):
    get, post = provider
    get.return_value.json = lambda: {"status": "OK", "results": [hotel(), hotel("6101 W Century Blvd, Los Angeles, CA 90045, USA", "hotel-2")]}
    response = create_quote_estimate(_request("Sheraton"), _session())
    assert response.resolution_type == "AMBIGUOUS_PLACE"
    assert len(response.resolution_suggestions) == 2
    assert response.estimated_min_amount is None
    post.assert_not_called()
    assert get.call_count == 1


@pytest.mark.parametrize("mutation", ["partial", "country", "city", "street", "type", "nan", "range", "missing_address"])
def test_unsafe_place_fails_closed(mutation, provider):
    get, post = provider
    result = deepcopy(hotel())
    if mutation == "partial": result["partial_match"] = True
    if mutation == "country": result["address_components"][-1]["short_name"] = "CA"
    if mutation == "city": result["address_components"] = [c for c in result["address_components"] if "locality" not in c["types"]]
    if mutation == "street": result["address_components"] = [c for c in result["address_components"] if "street_number" not in c["types"]]
    if mutation == "type": result["types"] = ["locality", "political"]
    if mutation == "nan": result["geometry"]["location"]["lat"] = "NaN"
    if mutation == "range": result["geometry"]["location"]["lat"] = 100
    if mutation == "missing_address": result.pop("formatted_address")
    get.return_value.json = lambda: {"status": "OK", "results": [result]}
    response = create_quote_estimate(_request("random invalid hotel abcxyz"), _session())
    assert response.estimated_min_amount is None
    assert response.resolution_type == "UNKNOWN_PLACE"
    assert "full street address" in response.resolution_message
    post.assert_not_called()


def test_vehicle_confirmation_keeps_numeric_fare(provider):
    request = _request("Anaheim Sheraton park")
    # Validate enum fields as a real API request would.
    from app.schemas.quote_estimate import QuoteEstimateCreate
    request = QuoteEstimateCreate(**{**request.model_dump(), "passenger_count": "3", "large_luggage_count": "4+", "child_seat_required": True})
    response = create_quote_estimate(request, _session())
    assert response.vehicle_assessment.value == "NEEDS_CONFIRMATION"
    assert response.estimated_min_amount is not None


def test_city_and_known_school_do_not_call_provider(provider):
    get, post = provider
    for raw in ["Anaheim", "UCLA"]:
        response = create_quote_estimate(_request(raw), _session())
        assert response.estimated_min_amount is not None
    get.assert_not_called()
    post.assert_not_called()


def test_full_address_keeps_exact_address_priority(provider):
    get, post = provider
    result = hotel()
    result["types"] = ["street_address"]
    get.return_value.json = lambda: {"status": "OK", "results": [result]}
    response = create_quote_estimate(_request(result["formatted_address"]), _session())
    assert response.estimated_min_amount is not None
    assert response.resolution_type != "VERIFIED_PLACE"
    assert get.call_count == post.call_count == 1


def test_ambiguity_cannot_create_customer_lead_or_order(monkeypatch):
    from app.services import quote_request_service as service
    from app.schemas.quote_request import QuoteRequestCreate
    from uuid import uuid4
    estimate = MagicMock(pricing_factors={"resolution_type": "AMBIGUOUS_PLACE"})
    monkeypatch.setattr(service, "get_valid_quote_estimate", lambda *_: estimate)
    customer = MagicMock()
    monkeypatch.setattr(service, "create_or_match_customer", customer)
    request = QuoteRequestCreate(estimate_id=uuid4(), customer_name="Test", phone="6265550100", estimate_acceptance=True)
    with pytest.raises(service.QuoteRequestError, match="AMBIGUOUS_LOCATION"):
        service.process_quote_request(_session(), request)
    customer.assert_not_called()


def test_zero_results_and_provider_timeout_do_not_route(provider):
    import requests
    get, post = provider
    get.return_value.json = lambda: {"status": "ZERO_RESULTS", "results": []}
    response = create_quote_estimate(_request("random invalid hotel abcxyz"), _session())
    assert response.resolution_type == "UNKNOWN_PLACE"
    get.side_effect = requests.Timeout()
    response = create_quote_estimate(_request("Hilton Anaheim"), _session())
    assert response.estimated_min_amount is None
    assert response.resolution_type == "UNKNOWN_PLACE"
    assert get.call_count == 2
    post.assert_not_called()


@pytest.mark.parametrize("kind", ["establishment", "lodging", "point_of_interest", "premise", "school", "university"])
def test_explicit_trusted_place_types(kind, provider):
    get, _ = provider
    result = hotel()
    result["types"] = [kind]
    result["address_components"] = [c for c in result["address_components"] if "postal_code" not in c["types"]]
    get.return_value.json = lambda: {"status": "OK", "results": [result]}
    assert create_quote_estimate(_request("Specific Public Destination"), _session()).estimated_min_amount is not None


@pytest.mark.parametrize("airport,service,raw,expected", [
    ("LAX", "AIRPORT_PICKUP", "Chino", (115,145)),
    ("LAX", "AIRPORT_PICKUP", "San Diego", (240,280)),
    ("LAX", "AIRPORT_DROPOFF", "San Diego", (240,280)),
    ("ONT", "AIRPORT_PICKUP", "Chino", (80,100)),
    ("ONT", "AIRPORT_PICKUP", "San Diego", (280,280)),
    ("ONT", "AIRPORT_PICKUP", "UC San Diego", (175,215)),
])
def test_required_archive_fares_are_unchanged(airport, service, raw, expected, provider):
    from app.schemas.quote_estimate import QuoteEstimateCreate
    request = QuoteEstimateCreate(**{**_request(raw).model_dump(), "airport_code": airport, "service_type": service})
    response = create_quote_estimate(request, _session())
    assert (response.estimated_min_amount, response.estimated_max_amount) == expected
    provider[0].assert_not_called()
    provider[1].assert_not_called()


def test_single_ranked_brand_is_not_proof_of_uniqueness(provider):
    response = create_quote_estimate(_request("Sheraton"), _session())
    assert response.estimated_min_amount is None
    provider[1].assert_not_called()


def test_unsafe_conflicting_candidate_blocks_unique_selection(provider):
    get, post = provider
    other = hotel()
    other["partial_match"] = True
    get.return_value.json = lambda: {"status": "OK", "results": [hotel(), other]}
    assert create_quote_estimate(_request("Sheraton Park Anaheim"), _session()).estimated_min_amount is None
    post.assert_not_called()


@pytest.mark.parametrize("raw", ["Anaheim Sheraton park", "尔湾 Marriott Hotel", "东谷 酒店"])
def test_place_details_never_collapse_to_city_alias(raw):
    assert normalize_location(raw)["normalized_city"] is None


def test_selected_place_address_is_reverified_before_route(provider):
    get, post = provider
    candidates = [hotel(), hotel("6101 W Century Blvd, Los Angeles, CA 90045, USA", "hotel-2")]
    get.return_value.json = lambda: {"status": "OK", "results": candidates}
    ambiguous = create_quote_estimate(_request("Sheraton"), _session())
    chosen = deepcopy(candidates[0])
    chosen["types"] = ["street_address"]
    get.return_value.json = lambda: {"status": "OK", "results": [chosen]}
    selected = create_quote_estimate(_request(ambiguous.resolution_suggestions[0].canonical_value), _session())
    assert selected.estimated_min_amount is not None
    assert get.call_count == 2
    assert post.call_count == 1


@pytest.mark.parametrize("raw", ["Anaheim", "Chino", "Irvine", "Riverside", "San Diego"])
def test_final_gate_city_preserves_archive_source(raw, provider):
    session = _session()
    response = create_quote_estimate(_request(raw), session)
    assert response.estimated_min_amount is not None
    source = session.add.call_args.args[0].pricing_source
    from app.services.approved_long_distance import APPROVED_LONG_DISTANCE_PRICING_SOURCE
    assert source == (APPROVED_LONG_DISTANCE_PRICING_SOURCE if raw == "San Diego" else "city_mileage_pricing_v1")
    provider[0].assert_not_called()
    provider[1].assert_not_called()


@pytest.mark.parametrize("airport,raw,place,expected", [
    ("LAX", "4255 Genesee Ave, San Diego, CA 92117", False, (240, 280)),
    ("ONT", "4255 Genesee Ave, San Diego, CA 92117", False, (280, 280)),
    ("LAX", "Specific San Diego Hotel", True, (240, 280)),
    ("ONT", "Specific San Diego Hotel", True, (280, 280)),
])
def test_final_gate_san_diego_approved_precedence(airport, raw, place, expected, provider, monkeypatch):
    from app.schemas.quote_estimate import QuoteEstimateCreate
    from app.services import quote_estimate_service as service
    from app.services.approved_long_distance import APPROVED_FIXED_ROUTE_PRICING_SOURCE, APPROVED_LONG_DISTANCE_PRICING_SOURCE
    result = hotel("4255 Genesee Ave, San Diego, CA 92117, USA", "san-diego-endpoint")
    for component in result["address_components"]:
        if component["types"] == ["locality"]: component["long_name"] = "San Diego"
        if component["types"] == ["postal_code"]: component["long_name"] = "92117"
    result["types"] = ["lodging"] if place else ["street_address"]
    provider[0].return_value.json = lambda: {"status": "OK", "results": [result]}
    if not place:
        # Explicit street syntax must never invoke the new resolver.
        place_search = MagicMock(side_effect=AssertionError("Address was intercepted by place search"))
        monkeypatch.setattr(service, "resolve_safe_place", place_search)
    request = QuoteEstimateCreate(**{**_request(raw).model_dump(), "airport_code": airport})
    session = _session()
    response = create_quote_estimate(request, session)
    assert (response.estimated_min_amount, response.estimated_max_amount) == expected
    assert session.add.call_args.args[0].pricing_source == (APPROVED_FIXED_ROUTE_PRICING_SOURCE if airport == "ONT" else APPROVED_LONG_DISTANCE_PRICING_SOURCE)
    assert response.is_fixed_fare == (airport == "ONT")
    assert provider[0].call_count == provider[1].call_count == 1
    if not place: place_search.assert_not_called()


@pytest.mark.parametrize("raw,results", [("Sheraton Park Anaheim", "unique"), ("Sheraton", "ambiguous"), ("random invalid hotel abcxyz", "none")])
def test_final_gate_estimate_has_no_business_record_side_effect(raw, results, provider):
    from app.models.quote_estimate import QuoteEstimate
    get, _ = provider
    values = [hotel()] if results == "unique" else [hotel(), hotel("6101 W Century Blvd, Los Angeles, CA 90045, USA", "hotel-2")] if results == "ambiguous" else []
    get.return_value.json = lambda: {"status": "OK" if values else "ZERO_RESULTS", "results": values}
    session = _session()
    create_quote_estimate(_request(raw), session)
    # The pre-existing estimate lifecycle persists only QuoteEstimate;
    # customer/lead/order/quote requests are exclusive to final confirmation.
    assert len(session.add.call_args_list) == 1
    assert isinstance(session.add.call_args.args[0], QuoteEstimate)
    session.add_all.assert_not_called()
