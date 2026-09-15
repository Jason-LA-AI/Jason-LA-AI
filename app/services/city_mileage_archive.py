"""Offline city-mileage archive lookup for airport quote estimates."""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path


ARCHIVE_PATH = Path(__file__).resolve().parents[1] / "data" / "airport_city_mileage_archive.json"

ALIASES = {
    "ucsd": "ucsandiego",
    "universityofcaliforniasandiego": "ucsandiego",
    "ucsdla jolla": "ucsandiego",
    "lasvegasnv": "lasvegas",
    "sanfranciscoca": "sanfrancisco",
}


@dataclass(frozen=True)
class ArchivedMileage:
    """A precomputed city-center route loop from the local archive."""

    total_miles: Decimal
    destination: str


def _key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return "".join(character for character in normalized.casefold() if character.isalnum())


@lru_cache
def _archive() -> dict:
    with ARCHIVE_PATH.open(encoding="utf-8") as file:
        return json.load(file)


def lookup_archived_mileage(
    *, service_type: str, airport_code: str, location: str
) -> ArchivedMileage | None:
    """Return a matching LAX/ONT city loop, or None for an unknown location."""

    lookup_key = ALIASES.get(_key(location), _key(location))
    profile = _archive()["profiles"].get(lookup_key)
    if profile is None:
        return None
    if not profile.get("route_available", True):
        return None
    airport = profile["airports"].get(airport_code)
    if airport is None:
        return None
    mileage_key = (
        "airport_pickup_miles"
        if service_type == "AIRPORT_PICKUP"
        else "airport_dropoff_miles"
    )
    return ArchivedMileage(
        total_miles=Decimal(str(airport[mileage_key])),
        destination=profile["destination"],
    )
