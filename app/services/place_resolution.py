"""Conservative, single-call Google place verification for quote endpoints."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import requests
from app.config.settings import settings
from app.services.route_pricing import GOOGLE_GEOCODING_URL, GeocodedAddress, RouteMileageUnavailable

ACCEPTED_PLACE_TYPES = frozenset({"establishment", "lodging", "point_of_interest", "premise", "school", "university"})

@dataclass(frozen=True)
class PlaceResolution:
    resolution_type: str
    endpoint: GeocodedAddress | None = None
    suggestions: tuple[dict[str, str], ...] = ()


def _safe_endpoint(result: dict) -> GeocodedAddress | None:
    if result.get("partial_match") or not ACCEPTED_PLACE_TYPES.intersection(result.get("types", [])):
        return None
    components = {t: c.get("long_name") for c in result.get("address_components", []) for t in c.get("types", [])}
    country = next((c.get("short_name") for c in result.get("address_components", []) if "country" in c.get("types", [])), None)
    city = components.get("locality") or components.get("postal_town")
    state = components.get("administrative_area_level_1")
    address = result.get("formatted_address")
    if country != "US" or not all((city, state, address, components.get("street_number"), components.get("route"))):
        return None
    if not isinstance(address, str) or len(address) > 240:
        return None
    try:
        point = result["geometry"]["location"]
        lat, lng = Decimal(str(point["lat"])), Decimal(str(point["lng"]))
        if not lat.is_finite() or not lng.is_finite() or not (-90 <= lat <= 90 and -180 <= lng <= 180):
            return None
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return None
    return GeocodedAddress(address, lat, lng, city, state, components.get("postal_code") or "", "US", result.get("place_id"))


def resolve_safe_place(raw: str) -> PlaceResolution:
    if not settings.google_maps_api_key:
        raise RouteMileageUnavailable("Place geocoding is not configured.")
    try:
        response = requests.get(GOOGLE_GEOCODING_URL, params={"address": raw, "key": settings.google_maps_api_key}, timeout=5)
        if not response.ok:
            raise RouteMileageUnavailable("Place geocoding failed.")
        payload = response.json()
        results = payload.get("results", [])
        if payload.get("status") != "OK" or not isinstance(results, list) or not results:
            return PlaceResolution("UNKNOWN_PLACE")
        if any(not isinstance(result, dict) for result in results):
            return PlaceResolution("UNKNOWN_PLACE")
        endpoints = [_safe_endpoint(result) for result in results]
        # A single returned candidate is required; unsafe conflicting candidates
        # still block automatic selection rather than being silently filtered out.
        if len(results) == 1 and endpoints[0]:
            # An unqualified one-word brand cannot prove uniqueness from a
            # geocoder's best-ranked single answer.
            if len(raw.split()) < 2:
                return PlaceResolution("UNKNOWN_PLACE")
            return PlaceResolution("VERIFIED_PLACE", endpoints[0])
        safe = {}
        for result, endpoint in zip(results, endpoints):
            if endpoint:
                identity = endpoint.place_id or endpoint.formatted_address
                safe[identity] = {"label": (result.get("name") or endpoint.formatted_address) + " — " + endpoint.city,
                                  "canonical_value": endpoint.formatted_address}
        if len(safe) >= 2:
            return PlaceResolution("AMBIGUOUS_PLACE", suggestions=tuple(list(safe.values())[:5]))
        return PlaceResolution("UNKNOWN_PLACE")
    except (requests.RequestException, ValueError, TypeError, AttributeError) as exc:
        raise RouteMileageUnavailable("Place geocoding is unavailable.") from exc
