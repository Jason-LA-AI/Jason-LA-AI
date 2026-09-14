"""Conservative ZIP and city normalization for V2.1 quote estimates."""

from __future__ import annotations

import re
from typing import Literal, TypedDict


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


ZIP_LOCATIONS: dict[str, tuple[str, str]] = {
    "91748": ("Rowland Heights", "ROWLAND_HEIGHTS"),
    "91789": ("Walnut", "WALNUT"),
}


CITY_LOCATIONS: dict[str, tuple[str, str]] = {
    "arcadia": ("Arcadia", "ARCADIA"),
    "chino": ("Chino", "CHINO"),
    "chino hills": ("Chino Hills", "CHINO_HILLS"),
    "ontario": ("Ontario", "ONTARIO"),
    "rancho cucamonga": ("Rancho Cucamonga", "RANCHO_CUCAMONGA"),
    "rowland heights": ("Rowland Heights", "ROWLAND_HEIGHTS"),
    "upland": ("Upland", "UPLAND"),
    "walnut": ("Walnut", "WALNUT"),
}


def normalize_location(location_input: str) -> NormalizedLocation:
    """Normalize a configured ZIP or city without guessing unknown places."""

    cleaned_input = " ".join(location_input.strip().split())
    if not cleaned_input:
        raise ValueError("location_input must not be empty")

    if ZIP_PATTERN.fullmatch(cleaned_input):
        matched_zip = ZIP_LOCATIONS.get(cleaned_input)
        if matched_zip:
            city, pricing_zone = matched_zip
            return {
                "input": cleaned_input,
                "input_type": "ZIP",
                "normalized_city": city,
                "postal_code": cleaned_input,
                "pricing_zone": pricing_zone,
            }
        return {
            "input": cleaned_input,
            "input_type": "ZIP",
            "normalized_city": None,
            "postal_code": cleaned_input,
            "pricing_zone": UNKNOWN_LOCATION,
        }

    matched_city = CITY_LOCATIONS.get(cleaned_input.casefold())
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
    if cleaned.casefold() in CITY_LOCATIONS:
        return False
    if STREET_ADDRESS_PATTERN.match(cleaned) or STREET_SUFFIX_PATTERN.search(cleaned):
        return True
    if PLACE_DETAIL_PATTERN.search(cleaned):
        return True

    # A multiword proper-place entry (for example, "The Getty") is useful to
    # review, while a single unqualified word remains too ambiguous.
    words = re.findall(r"[A-Za-z][A-Za-z'.-]*", cleaned)
    return len(words) >= 2 and len(cleaned) >= 6
