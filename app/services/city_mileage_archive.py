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
    "ucsdlajolla": "ucsandiego",
    "lasvegasnv": "lasvegas",
    "sanfranciscoca": "sanfrancisco",
    "senbernardino": "sanbernardino",
    "sanbernadino": "sanbernardino",
    "renchocucamonga": "ranchocucamonga",
    "dtla": "downtownlosangeles",
    "downtownla": "downtownlosangeles",
    "uclacampus": "ucla",
    "usccampus": "usc",
    "ucirvinecampus": "ucirvine",
    "ucriversidecampus": "ucriverside",
    "callutheranuniversity": "callutheran",
    "smc": "santamonicacollege",
    "disneylandresort": "disneyland",
}


@dataclass(frozen=True)
class ArchivedMileage:
    """A precomputed city-center route loop from the local archive."""

    total_miles: Decimal
    destination: str
    leg_1_miles: Decimal | None = None
    leg_2_miles: Decimal | None = None
    leg_3_miles: Decimal | None = None


def canonical_location_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return "".join(character for character in normalized.casefold() if character.isalnum())


def canonical_archive_key(value: str) -> str:
    """Return an explicitly configured alias or canonical archive key."""

    raw_key = canonical_location_key(value)
    return ALIASES.get(raw_key, raw_key)


@lru_cache
def _archive() -> dict:
    with ARCHIVE_PATH.open(encoding="utf-8") as file:
        return json.load(file)


def supported_destinations() -> dict[str, str]:
    """Return canonical archive keys and display names for safe normalization."""

    return {
        key: str(profile["destination"])
        for key, profile in _archive()["profiles"].items()
    }


def lookup_archived_mileage(
    *, service_type: str, airport_code: str, location: str
) -> ArchivedMileage | None:
    """Return a matching LAX/ONT city loop, or None for an unknown location."""

    lookup_key = canonical_archive_key(location)
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
    legs = airport.get(
        "airport_pickup_legs_miles"
        if service_type == "AIRPORT_PICKUP"
        else "airport_dropoff_legs_miles"
    )
    if not isinstance(legs, list) or len(legs) != 3:
        return None
    return ArchivedMileage(
        total_miles=Decimal(str(airport[mileage_key])),
        destination=profile["destination"],
        leg_1_miles=Decimal(str(legs[0])),
        leg_2_miles=Decimal(str(legs[1])),
        leg_3_miles=Decimal(str(legs[2])),
    )
