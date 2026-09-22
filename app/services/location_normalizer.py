"""Conservative ZIP and city normalization for V2.1 quote estimates."""

from __future__ import annotations

import re
import unicodedata
from typing import Literal, TypedDict

from app.services.city_mileage_archive import (
    canonical_archive_key,
    canonical_location_key,
    supported_destinations,
)


UNKNOWN_LOCATION = "UNKNOWN_LOCATION"
ZIP_PATTERN = re.compile(r"^\d{5}(?:-\d{4})?$")
CITY_STATE_PATTERN = re.compile(
    r"^(?P<city>.+?)(?:,?\s+)(?P<state>CA|California|NV|Nevada)(?:\s+(?P<zip>\d{5}))?$",
    re.IGNORECASE,
)
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
    resolution_type: str
    resolution_reason: str | None


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

# Direct aliases are finite, reviewed identity mappings.  They never contain
# prices and target only destinations already present in the runtime archive.
CHINESE_SAFE_ALIASES = {
    "罗兰岗": "Rowland Heights", "罗兰高地": "Rowland Heights", "东谷": "Eastvale",
    "奇诺": "Chino", "尔湾": "Irvine", "河滨": "Riverside", "莫雷诺谷": "Moreno Valley",
    "圣贝纳迪诺": "San Bernardino", "圣地亚哥": "San Diego", "旧金山": "San Francisco",
    "拉斯维加斯": "Las Vegas", "圣塔芭芭拉": "Santa Barbara", "圣巴巴拉": "Santa Barbara",
    "帕萨迪纳": "Pasadena", "阿罕布拉": "Alhambra", "圣盖博": "San Gabriel", "核桃市": "Walnut",
    "迪士尼乐园": "Disneyland", "洛杉矶市中心": "Downtown Los Angeles",
    "加州大学圣地亚哥分校": "UC San Diego", "UC圣地亚哥": "UC San Diego",
}
AMBIGUOUS_ABBREVIATIONS = {"sb": ("San Bernardino", "Santa Barbara"), "la": (), "oc": (), "ie": ()}

# The verified archive is a California service-area archive, with the one
# approved Nevada destination recorded explicitly.  This is state metadata,
# not a city-alias list: all other archive destinations remain CA by policy.
DESTINATION_STATE_OVERRIDES = {"Las Vegas": "NV"}
STATE_NAMES = {"ca": "CA", "california": "CA", "nv": "NV", "nevada": "NV"}


def _expected_state(destination: str) -> str:
    return DESTINATION_STATE_OVERRIDES.get(destination, "CA")


def _clean_input(value: str) -> str:
    """Normalize presentation Unicode without guessing a location."""
    value = unicodedata.normalize("NFKC", value).replace("，", ",").replace("、", ",")
    return " ".join(value.strip().split())


def _direct_alias_destination(cleaned: str) -> str | None:
    cleaned = cleaned.strip(" ,.;")
    if cleaned in CHINESE_SAFE_ALIASES:
        target = CHINESE_SAFE_ALIASES[cleaned]
        return target if canonical_archive_key(target) in CITY_LOCATIONS else None
    # Safe bilingual form: both portions must resolve to exactly one target.
    candidates = {target for alias, target in CHINESE_SAFE_ALIASES.items() if alias in cleaned}
    if not candidates:
        return None
    english = re.sub("|".join(map(re.escape, CHINESE_SAFE_ALIASES)), " ", cleaned)
    english_match = CITY_LOCATIONS.get(canonical_archive_key(english))
    if english_match:
        candidates.add(english_match[0])
    return candidates.pop() if len(candidates) == 1 else None


def _has_conflicting_bilingual_destination(cleaned: str) -> bool:
    chinese_targets = {target for alias, target in CHINESE_SAFE_ALIASES.items() if alias in cleaned}
    if not chinese_targets:
        return False
    english = re.sub("|".join(map(re.escape, CHINESE_SAFE_ALIASES)), " ", cleaned)
    english_match = CITY_LOCATIONS.get(canonical_archive_key(english))
    return bool(english_match and any(target != english_match[0] for target in chinese_targets))


def _city_state_parts(cleaned_input: str) -> tuple[str, str | None, str | None]:
    """Parse a city/state form without treating an address as a city.

    ZIP-bearing forms remain conservative until a ZIP-to-city source exists.
    """

    if STREET_ADDRESS_PATTERN.match(cleaned_input) or STREET_SUFFIX_PATTERN.search(cleaned_input):
        return cleaned_input, None, None
    match = CITY_STATE_PATTERN.fullmatch(cleaned_input)
    if not match:
        return cleaned_input, None, None
    return (
        " ".join(match.group("city").split()),
        STATE_NAMES[match.group("state").casefold()],
        match.group("zip"),
    )


def normalize_location(location_input: str) -> NormalizedLocation:
    """Normalize a configured ZIP or city without guessing unknown places."""

    cleaned_input = _clean_input(location_input)
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
            "resolution_type": "ZIP_NEEDS_CITY",
            "resolution_reason": "ZIP_NEEDS_CITY",
        }

    direct_alias = _direct_alias_destination(cleaned_input)
    if direct_alias:
        city, pricing_zone = CITY_LOCATIONS[canonical_archive_key(direct_alias)]
        return {"input": cleaned_input, "input_type": "CITY", "normalized_city": city,
                "postal_code": None, "pricing_zone": pricing_zone,
                "resolution_type": "SAFE_CHINESE_ALIAS", "resolution_reason": None}
    if _has_conflicting_bilingual_destination(cleaned_input):
        return {"input": cleaned_input, "input_type": "CITY", "normalized_city": None,
                "postal_code": None, "pricing_zone": UNKNOWN_LOCATION,
                "resolution_type": "INVALID_LOCATION", "resolution_reason": "CONFLICTING_BILINGUAL_DESTINATION"}

    city_part, stated_state, stated_zip = _city_state_parts(cleaned_input)
    # ZIP-bearing city/state input cannot be safely validated yet.  Do not
    # infer that a ZIP belongs to the stated city merely because both look
    # plausible.
    if stated_zip:
        return {
            "input": cleaned_input,
            "input_type": "CITY",
            "normalized_city": None,
            "postal_code": stated_zip,
            "pricing_zone": UNKNOWN_LOCATION,
            "resolution_type": "CITY_ZIP_VALIDATION_REQUIRED",
            "resolution_reason": "CITY_ZIP_VALIDATION_REQUIRED",
        }

    # Explicit aliases maintained by the mileage archive remain eligible for
    # direct pricing because they are known, unambiguous customer inputs.
    matched_city = CITY_LOCATIONS.get(canonical_archive_key(city_part))
    if matched_city:
        city, pricing_zone = matched_city
        if stated_state and stated_state != _expected_state(city):
            return {
                "input": cleaned_input,
                "input_type": "CITY",
                "normalized_city": None,
                "postal_code": None,
                "pricing_zone": UNKNOWN_LOCATION,
                "resolution_type": "INVALID_LOCATION",
                "resolution_reason": "STATE_MISMATCH",
            }
        return {
            "input": cleaned_input,
            "input_type": "CITY",
            "normalized_city": city,
            "postal_code": None,
            "pricing_zone": pricing_zone,
            "resolution_type": "CANONICAL_DIRECT",
            "resolution_reason": None,
        }

    resolution_type = (
        "EXACT_ADDRESS_CANDIDATE"
        if is_exact_address_candidate(cleaned_input)
        else "NEEDS_DISAMBIGUATION"
        if canonical_location_key(cleaned_input) in AMBIGUOUS_ABBREVIATIONS
        else "UNKNOWN_LOCATION"
    )
    return {
        "input": cleaned_input,
        "input_type": "CITY",
        "normalized_city": None,
        "postal_code": None,
        "pricing_zone": UNKNOWN_LOCATION,
        "resolution_type": resolution_type,
        "resolution_reason": "AMBIGUOUS_ABBREVIATION" if resolution_type == "NEEDS_DISAMBIGUATION" else None,
    }


def suggest_location(location_input: str) -> LocationSuggestion | None:
    """Return an explicit, safe replacement for a non-canonical place name.

    Suggestions are presentation-only: callers must re-submit the returned
    canonical_location before pricing it.  ZIP-only and street-address inputs
    are categorically excluded so they cannot be downgraded to a city center.
    """

    cleaned_input = _clean_input(location_input)
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
        candidate = _safe_typo_suggestion(cleaned_input)
        if candidate is None:
            return None
        return {"canonical_location": candidate, "display_name": candidate}

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


def _edit_distance(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for index, char in enumerate(left, 1):
        current = [index]
        for other_index, other in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[other_index] + 1, previous[other_index - 1] + (char != other)))
        previous = current
    return previous[-1]


def _safe_typo_suggestion(cleaned: str) -> str | None:
    key = canonical_location_key(cleaned)
    if len(key) < 5 or key in AMBIGUOUS_ABBREVIATIONS:
        return None
    max_distance = 1 if len(key) <= 8 else 2 if len(key) <= 14 else 3
    ranked = sorted((min(_edit_distance(key, candidate), 1 if _is_adjacent_transpose(key, candidate) else 99), name) for candidate, name in supported_destinations().items())
    if not ranked or ranked[0][0] > max_distance:
        return None
    if len(ranked) > 1 and ranked[1][0] <= ranked[0][0] + 1:
        return None
    return ranked[0][1]


def _is_adjacent_transpose(left: str, right: str) -> bool:
    if len(left) != len(right):
        return False
    differences = [index for index, (a, b) in enumerate(zip(left, right)) if a != b]
    return len(differences) == 2 and differences[1] == differences[0] + 1 and left[differences[0]] == right[differences[1]] and left[differences[1]] == right[differences[0]]


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


def is_exact_address_candidate(location_input: str) -> bool:
    """Return whether input warrants strict live address verification.

    This is deliberately a narrow syntax gate, not an authorization to price:
    the provider must still return one complete, unambiguous US address.
    """

    cleaned = " ".join(location_input.strip().split())
    return bool(
        cleaned
        and not ZIP_PATTERN.fullmatch(cleaned)
        and STREET_ADDRESS_PATTERN.match(cleaned)
        and STREET_SUFFIX_PATTERN.search(cleaned)
    )
