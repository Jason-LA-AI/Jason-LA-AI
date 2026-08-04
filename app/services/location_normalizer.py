"""Conservative ZIP and city normalization for V2.1 quote estimates."""

from __future__ import annotations

import re
from typing import Literal, TypedDict


UNKNOWN_LOCATION = "UNKNOWN_LOCATION"
ZIP_PATTERN = re.compile(r"^\d{5}$")


class NormalizedLocation(TypedDict):
    """Normalized location values used by the estimate service."""

    input: str
    input_type: Literal["ZIP", "CITY"]
    normalized_city: str | None
    postal_code: str | None
    pricing_zone: str


ZIP_LOCATIONS: dict[str, tuple[str, str]] = {
    "91748": ("Rowland Heights", "ROWLAND_HEIGHTS"),
}


CITY_LOCATIONS: dict[str, tuple[str, str]] = {
    "rowland heights": ("Rowland Heights", "ROWLAND_HEIGHTS"),
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
