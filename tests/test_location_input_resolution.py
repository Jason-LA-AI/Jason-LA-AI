"""Offline Phase 2A resolution safety tests."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.schemas.quote_estimate import QuoteEstimateCreate
from app.services.location_normalizer import normalize_location, suggest_location
from app.services.quote_estimate_service import create_quote_estimate
from unittest.mock import MagicMock
from uuid import uuid4


def _session():
    session = MagicMock()
    session.refresh.side_effect = lambda estimate: setattr(estimate, "id", uuid4())
    return session


def _request(location):
    return QuoteEstimateCreate(service_type="AIRPORT_PICKUP", airport_code="LAX", service_date=datetime.now(ZoneInfo("America/Los_Angeles")).date(), service_time="12:00", location_input=location, passenger_count="2", large_luggage_count="1", child_seat_required=False, oversized_items=False)


@pytest.mark.parametrize(("raw", "canonical"), [("东谷", "Eastvale"), ("圣地亚哥，", "San Diego"), ("旧金山", "San Francisco"), ("拉斯维加斯", "Las Vegas"), ("加州大学圣地亚哥分校", "UC San Diego"), ("UC圣地亚哥", "UC San Diego")])
def test_chinese_safe_aliases_directly_resolve(raw, canonical):
    assert normalize_location(raw)["normalized_city"] == canonical


@pytest.mark.parametrize(("raw", "expected"), [
    ("圣地亚哥", ("240", "280")),
    ("旧金山", ("850", "1000")),
    ("拉斯维加斯", ("500", "750")),
    ("圣塔芭芭拉", ("220", "260")),
    ("UC圣地亚哥", ("185", "225")),
])
def test_chinese_approved_routes_keep_canonical_directional_ranges(raw, expected):
    response = create_quote_estimate(_request(raw), _session())
    assert (str(response.estimated_min_amount), str(response.estimated_max_amount)) == expected


@pytest.mark.parametrize(("raw", "canonical"), [("San Diego 圣地亚哥", "San Diego"), ("东谷 Eastvale", "Eastvale")])
def test_same_destination_bilingual_input_resolves(raw, canonical):
    assert normalize_location(raw)["normalized_city"] == canonical


def test_conflicting_bilingual_input_fails_closed():
    assert normalize_location("San Diego 东谷")["normalized_city"] is None


@pytest.mark.parametrize(("raw", "expected_type", "phrase"), [
    ("LA", "NEEDS_DISAMBIGUATION", "Los Angeles-area city"),
    ("OC", "NEEDS_DISAMBIGUATION", "Orange County city"),
    ("IE", "NEEDS_DISAMBIGUATION", "Inland Empire city"),
])
def test_regional_abbreviations_require_a_specific_city(raw, expected_type, phrase):
    response = create_quote_estimate(_request(raw), _session())
    assert response.estimated_min_amount is None
    assert response.resolution_type == expected_type
    assert phrase in (response.resolution_message or "")
    assert response.resolution_suggestions == []


def test_sb_offers_exactly_two_safe_disambiguation_choices():
    response = create_quote_estimate(_request("SB"), _session())
    assert response.estimated_min_amount is None
    assert response.resolution_type == "NEEDS_DISAMBIGUATION"
    assert [(item.label, item.canonical_value) for item in response.resolution_suggestions] == [
        ("San Bernardino", "San Bernardino"),
        ("Santa Barbara", "Santa Barbara"),
    ]


@pytest.mark.parametrize(("raw", "resolution_type"), [("92880", "ZIP_NEEDS_CITY"), ("92880-1234", "ZIP_NEEDS_CITY"), ("San Diego, CA 92117", "CITY_ZIP_VALIDATION_REQUIRED")])
def test_zip_guidance_never_prices_or_guesses_a_city(raw, resolution_type):
    response = create_quote_estimate(_request(raw), _session())
    assert response.estimated_min_amount is None
    assert response.resolution_type == resolution_type
    assert response.resolution_message and "/" in response.resolution_message


def test_full_address_never_normalizes_to_a_city_center():
    normalized = normalize_location("13820 Schleisman Rd, Eastvale, CA 92880")
    assert normalized["normalized_city"] is None
    assert normalized["resolution_type"] == "EXACT_ADDRESS_CANDIDATE"
    assert suggest_location("13820 Schleisman Rd, Eastvale, CA 92880") is None


@pytest.mark.parametrize(("raw", "canonical"), [("Riversdie", "Riverside"), ("Morreno Valley", "Moreno Valley"), ("Sant Barbara", "Santa Barbara"), ("Irvnie", "Irvine")])
def test_typos_offer_only_a_safe_suggestion(raw, canonical):
    suggestion = suggest_location(raw)
    assert suggestion and suggestion["canonical_location"] == canonical
    assert create_quote_estimate(_request(raw), _session()).estimated_min_amount is None


@pytest.mark.parametrize("raw", ["SB", "LA", "OC", "IE", "92880", "92880-1234"])
def test_ambiguous_and_zip_inputs_never_suggest_or_price(raw):
    assert suggest_location(raw) is None
    assert normalize_location(raw)["normalized_city"] is None
