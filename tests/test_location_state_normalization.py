"""Phase 1 safety coverage for structured city/state normalization."""

import pytest

from app.services.location_normalizer import UNKNOWN_LOCATION, normalize_location


@pytest.mark.parametrize(
    ("input_text", "canonical"),
    [
        ("San Bernardino, CA", "San Bernardino"),
        ("San Bernardino CA", "San Bernardino"),
        ("San Bernardino, California", "San Bernardino"),
        ("  san  bernardino,   ca ", "San Bernardino"),
        ("Las Vegas, NV", "Las Vegas"),
        ("Las Vegas Nevada", "Las Vegas"),
        ("UC San Diego, CA", "UC San Diego"),
        ("San Diego, CA", "San Diego"),
    ],
)
def test_safe_city_state_forms_resolve_to_their_canonical_destination(input_text, canonical):
    assert normalize_location(input_text)["normalized_city"] == canonical


@pytest.mark.parametrize(
    "input_text",
    ["San Bernardino, TX", "Moreno Valley, NV", "San Diego, NV", "San Francisco, NV", "Las Vegas, CA", "Santa Barbara, NV", "Ontario, Canada", "Las Vegas, NM", "SB", "LA", "OC", "IE"],
)
def test_wrong_state_and_ambiguous_inputs_fail_closed(input_text):
    location = normalize_location(input_text)
    assert location["normalized_city"] is None
    assert location["pricing_zone"] == UNKNOWN_LOCATION


@pytest.mark.parametrize(
    "input_text",
    ["13820 Schleisman Rd, Eastvale, CA 92880", "4255 Genesee Ave, San Diego, CA 92117"],
)
def test_full_addresses_are_not_reduced_to_city_state_inputs(input_text):
    location = normalize_location(input_text)
    assert location["normalized_city"] is None
    assert location["input"] == input_text
