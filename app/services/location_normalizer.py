"""Conservative ZIP and city normalization for V2.1 quote estimates."""

from __future__ import annotations

import re
from typing import Literal, TypedDict

from app.services.city_mileage_archive import (
    canonical_archive_key,
    canonical_location_key,
    supported_destinations,
)


UNKNOWN_LOCATION = "UNKNOWN_LOCATION"
ZIP_PATTERN = re.compile(r"^\d{5}$")
STREET_ADDRESS_PATTERN = re.compile(r"^\d+[\w-]*(?:\s|,).+")
STREET_SUFFIX_PATTERN = re.compile(
    r"\b(?:street|st|avenue|ave|road|rd|boulevard|blvd|drive|dr|lane|ln|way|place|pl|court|ct)\b",
    re.IGNORECASE,
)
PLACE_DETAIL_PATTERN = re.compile(
    r"\b(?:hotel|inn|resort|suites|university|college|school|campus|dorm|apartment|apt|building|tower|terminal|station|mall|center|centre|plaza|park)\b",
    re.IGNORECASE,
)


class NormalizedLocation(TypedDict):
    """Normalized location values used by the estimate service."""

    input: str
    input_type: Literal["ZIP", "CITY"]
    normalized_city: str | None
    postal_code: str | None
    pricing_zone: str


class LocationSuggestion(TypedDict):
    """A click-to-confirm replacement; never a pricing authorization."""

    canonical_location: str
    display_name: str


def _pricing_zone(name: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")


# This is derived from the locally verified road-mileage archive, so a city
# that normalizes here has a matching closed-loop road route rather than a
# generic zone-price fallback.
CITY_LOCATIONS: dict[str, tuple[str, str]] = {
    key: (name, _pricing_zone(name))
    for key, name in supported_destinations().items()
}

# These are deliberately explicit, finite mappings.  They supplement the
# maintained aliases in city_mileage_archive and are not edit-distance or AI
# guesses.  Airport suggestions clarify the user's wording, but are not archive
# locations and therefore still require a new estimate to prove eligibility.
CURATED_SUGGESTION_KEYS = {
    "downtown": "downtownlosangeles",
    "disney": "disneyland",
    "ontarioairport": "ONT",
    "laairport": "LAX",
}
SUGGESTION_DISPLAY_NAMES = {
    "downtown": "Downtown Los Angeles (DTLA)",
    "ontarioairport": "ONT",
    "laairport": "LAX",
}


def normalize_location(location_input: str) -> NormalizedLocation:
    """Normalize a configured ZIP or city without guessing unknown places."""

    cleaned_input = " ".join(location_input.strip().split())
    if not cleaned_input:
        raise ValueError("location_input must not be empty")

    if ZIP_PATTERN.fullmatch(cleaned_input):
        # ZIP coverage is wider than a verified city-center or landmark route.
        # Never turn a ZIP-only request into a neighboring archive estimate;
        # exact-route pricing is not enabled yet.
        return {
            "input": cleaned_input,
            "input_type": "ZIP",
            "normalized_city": None,
            "postal_code": cleaned_input,
            "pricing_zone": UNKNOWN_LOCATION,
        }

    # Explicit aliases maintained by the mileage archive remain eligible for
    # direct pricing because they are known, unambiguous customer inputs.
    matched_city = CITY_LOCATIONS.get(canonical_archive_key(cleaned_input))
    if matched_city:
        city, pricing_zone = matched_city
        return {
            "input": cleaned_input,
            "input_type": "CITY",
            "normalized_city": city,
            "postal_code": None,
            "pricing_zone": pricing_zone,
        }

    return {
        "input": cleaned_input,
        "input_type": "CITY",
        "normalized_city": None,
        "postal_code": None,
        "pricing_zone": UNKNOWN_LOCATION,
    }


def suggest_location(location_input: str) -> LocationSuggestion | None:
    """Return an explicit, safe replacement for a non-canonical place name.

    Suggestions are presentation-only: callers must re-submit the returned
    canonical_location before pricing it.  ZIP-only and street-address inputs
    are categorically excluded so they cannot be downgraded to a city center.
    """

    cleaned_input = " ".join(location_input.strip().split())
    if (
        not cleaned_input
        or ZIP_PATTERN.fullmatch(cleaned_input)
        or STREET_ADDRESS_PATTERN.match(cleaned_input)
        or STREET_SUFFIX_PATTERN.search(cleaned_input)
    ):
        return None

    raw_key = canonical_location_key(cleaned_input)
    if canonical_archive_key(cleaned_input) in CITY_LOCATIONS:
        # Canonical archive locations and explicit safe aliases price normally.
        return None

    target_key = CURATED_SUGGESTION_KEYS.get(raw_key)
    if target_key is None:
        return None

    matched_city = CITY_LOCATIONS.get(target_key)
    if matched_city:
        canonical_location = matched_city[0]
        return {
            "canonical_location": canonical_location,
            "display_name": SUGGESTION_DISPLAY_NAMES.get(raw_key, canonical_location),
        }

    # ONT and LAX are intentionally offered only as explicit airport labels.
    # They are not archive destinations, so accepting either still cannot
    # produce a city-center numeric fare.
    if target_key in {"ONT", "LAX"}:
        return {
            "canonical_location": target_key,
            "display_name": SUGGESTION_DISPLAY_NAMES[raw_key],
        }
    return None


def location_has_sufficient_detail(location_input: str) -> bool:
    """Return whether free-text location can identify a real trip endpoint.

    This deliberately does not require a US mailing-address format.  A street
    address, hotel, school, campus, apartment/dorm, or descriptive place name
    can be enough for Jason to review a route.  A ZIP code or a configured city
    name alone cannot identify the actual pickup or drop-off point.
    """

    cleaned = " ".join(location_input.strip().split())
    if not cleaned or ZIP_PATTERN.fullmatch(cleaned):
        return False
    if canonical_archive_key(cleaned) in CITY_LOCATIONS:
        return False
    if STREET_ADDRESS_PATTERN.match(cleaned) or STREET_SUFFIX_PATTERN.search(cleaned):
        return True
    if PLACE_DETAIL_PATTERN.search(cleaned):
        return True

    # A multiword proper-place entry (for example, "The Getty") is useful to
    # review, while a single unqualified word remains too ambiguous.
    words = re.findall(r"[A-Za-z][A-Za-z'.-]*", cleaned)
    return len(words) >= 2 and len(cleaned) >= 6
