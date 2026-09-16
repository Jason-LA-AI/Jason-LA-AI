"""Create the offline airport mileage archive used by the quote service.

This maintenance tool makes a small, one-time set of read-only requests using
public city-center coordinates and a public OpenStreetMap road router.  The
website itself only reads the generated JSON file; it never calls that router.
"""

from __future__ import annotations

import argparse
import csv
import json
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests


CITY_COORDINATE_DATASET_URL = (
    "https://raw.githubusercontent.com/kelvins/US-Cities-Database/main/"
    "csv/us_cities.csv"
)
OSRM_TABLE_URL = "https://router.project-osrm.org/table/v1/driving/"
OPEN_METEO_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
USER_AGENT = "Jason-LA-AI offline mileage archive builder"
METERS_PER_MILE = 1609.344

# Los Angeles County's 88 incorporated cities. Unincorporated communities are
# intentionally kept out of this first archive because their boundaries are
# not city-level destinations.
LOS_ANGELES_COUNTY_CITIES = (
    "Agoura Hills", "Alhambra", "Arcadia", "Artesia", "Avalon", "Azusa",
    "Baldwin Park", "Bell", "Bell Gardens", "Bellflower", "Beverly Hills",
    "Bradbury", "Burbank", "Calabasas", "Carson", "Cerritos", "Claremont",
    "Commerce", "Compton", "Covina", "Cudahy", "Culver City", "Diamond Bar",
    "Downey", "Duarte", "El Monte", "El Segundo", "Gardena", "Glendale",
    "Glendora", "Hawaiian Gardens", "Hawthorne", "Hermosa Beach", "Hidden Hills",
    "Huntington Park", "City of Industry", "Inglewood", "Irwindale",
    "La Cañada Flintridge", "La Habra Heights", "La Mirada", "La Puente",
    "La Verne", "Lakewood", "Lancaster", "Lawndale", "Lomita", "Long Beach",
    "Los Angeles", "Lynwood", "Malibu", "Manhattan Beach", "Maywood", "Monrovia",
    "Montebello", "Monterey Park", "Norwalk", "Palmdale", "Palos Verdes Estates",
    "Paramount", "Pasadena", "Pico Rivera", "Pomona", "Rancho Palos Verdes",
    "Redondo Beach", "Rolling Hills", "Rolling Hills Estates", "Rosemead", "San Dimas",
    "San Fernando", "San Gabriel", "San Marino", "Santa Clarita", "Santa Fe Springs",
    "Santa Monica", "Sierra Madre", "Signal Hill", "South El Monte", "South Gate",
    "South Pasadena", "Temple City", "Torrance", "Vernon", "Walnut", "West Covina",
    "West Hollywood", "Westlake Village", "Whittier",
)

# Additional municipal destinations requested for the airport-pricing coverage.
# These are resolved from the same public California city-centre dataset as the
# Los Angeles County cities above; they are not hand-entered mileage values.
REQUESTED_CALIFORNIA_CITIES = (
    "Chino", "Chino Hills", "Ontario", "Rancho Cucamonga", "Fontana",
    "Riverside", "Moreno Valley", "San Bernardino", "Eastvale", "Corona",
    "Redlands", "Upland", "Anaheim", "Fullerton", "Buena Park",
    "Garden Grove", "Irvine", "Costa Mesa", "Newport Beach", "Laguna Beach",
    "Lake Forest", "Aliso Viejo", "Santa Ana",
)

# Public landmark/city reference points requested by Jason. These points are
# deliberately venue/city centers, not customer street addresses.
SPECIAL_DESTINATIONS = {
    # Rowland Heights is the base and an unincorporated community, so it is
    # explicitly included even though the main city list is incorporated only.
    "Rowland Heights": (-117.9053, 33.9761),
    "Las Vegas": (-115.1728, 36.1147),
    "UC San Diego": (-117.2340, 32.8801),
    "San Francisco": (-122.4194, 37.7749),
    # Requested neighborhood and campus reference points.  A city-centre or
    # named-campus point is only used when the customer enters that place name;
    # full addresses continue to require live Google road routing.
    "Downtown Los Angeles": (-118.2468, 34.0407),
    "Koreatown": (-118.3089, 34.0583),
    "Hollywood": (-118.3287, 34.0928),
    "Venice": (-118.4695, 33.9850),
    "Westchester": (-118.3965, 33.9597),
    "Hacienda Heights": (-117.9690, 33.9950),
    "Disneyland": (-117.9190, 33.8121),
    "UCLA": (-118.4452, 34.0689),
    "USC": (-118.2851, 34.0224),
    "UC Irvine": (-117.8443, 33.6405),
    "UC Riverside": (-117.3281, 33.9737),
    "Cal Lutheran": (-118.8795, 34.2256),
    "Santa Monica College": (-118.4705, 34.0187),
    "LAX Area": (-118.4085, 33.9416),
}

NO_DRIVING_ROUTE_CITIES = {"Avalon"}

REFERENCE_POINTS = {
    "BASE": (-117.9053, 33.9761),  # Rowland Heights city center
    "LAX": (-118.4085, 33.9416),
    "ONT": (-117.6012, 34.0560),
}


def canonical_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return "".join(character for character in normalized.casefold() if character.isalnum())


def california_city_points() -> dict[str, tuple[float, float]]:
    response = requests.get(
        CITY_COORDINATE_DATASET_URL,
        timeout=30,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    points: dict[str, tuple[float, float]] = {}
    for row in csv.DictReader(response.text.splitlines()):
        if row["STATE_CODE"] != "CA":
            continue
        points[canonical_key(row["CITY"])] = (
            float(row["LONGITUDE"]),
            float(row["LATITUDE"]),
        )
    return points


def city_center_from_public_geocoder(city: str) -> tuple[float, float]:
    """Resolve only a missing public municipality, never a customer address."""

    response = requests.get(
        OPEN_METEO_GEOCODING_URL,
        params={"name": f"{city}, California", "count": 5, "language": "en", "format": "json"},
        timeout=30,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    results = response.json().get("results") or []
    for result in results:
        if result.get("country_code") == "US" and result.get("admin1") == "California":
            return (float(result["longitude"]), float(result["latitude"]))
    raise RuntimeError(f"No California city center found for {city}")


def distances(
    points: list[tuple[float, float]], sources: list[int], destinations: list[int]
) -> list[list[float]]:
    coordinate_text = ";".join(f"{longitude},{latitude}" for longitude, latitude in points)
    response = requests.get(
        OSRM_TABLE_URL + coordinate_text,
        params={
            "sources": ";".join(map(str, sources)),
            "destinations": ";".join(map(str, destinations)),
            "annotations": "distance",
        },
        timeout=60,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    values = response.json().get("distances")
    if not isinstance(values, list):
        raise RuntimeError("Road router returned no distance matrix.")
    missing = [
        f"source={sources[row_index]} destination={destinations[column_index]}"
        for row_index, row in enumerate(values)
        for column_index, value in enumerate(row)
        if value is None
    ]
    if missing:
        raise RuntimeError("Road router returned no route for " + ", ".join(missing))
    return values


def airport_profiles(
    airport_code: str, destination_points: list[tuple[float, float]]
) -> list[dict[str, float]]:
    points = [REFERENCE_POINTS["BASE"], REFERENCE_POINTS[airport_code], *destination_points]
    destination_indexes = list(range(2, len(points)))
    base_to_airport = distances(points, [0], [1])[0][0]
    airport_to_base = distances(points, [1], [0])[0][0]
    airport_to_destination = distances(points, [1], destination_indexes)[0]
    destination_to_base = [row[0] for row in distances(points, destination_indexes, [0])]
    base_to_destination = distances(points, [0], destination_indexes)[0]
    destination_to_airport = [row[0] for row in distances(points, destination_indexes, [1])]

    profiles = []
    for index in range(len(destination_points)):
        pickup_legs_meters = (
            base_to_airport,
            airport_to_destination[index],
            destination_to_base[index],
        )
        dropoff_legs_meters = (
            base_to_destination[index],
            destination_to_airport[index],
            airport_to_base,
        )
        profiles.append(
            {
                "airport_pickup_miles": round(
                    sum(pickup_legs_meters)
                    / METERS_PER_MILE,
                    1,
                ),
                "airport_dropoff_miles": round(
                    sum(dropoff_legs_meters)
                    / METERS_PER_MILE,
                    1,
                ),
                "airport_pickup_legs_miles": [
                    round(value / METERS_PER_MILE, 1) for value in pickup_legs_meters
                ],
                "airport_dropoff_legs_miles": [
                    round(value / METERS_PER_MILE, 1) for value in dropoff_legs_meters
                ],
            }
        )
    return profiles


def build_archive() -> dict[str, Any]:
    census_points = california_city_points()
    requested_cities = tuple(
        city for city in REQUESTED_CALIFORNIA_CITIES
        if city not in LOS_ANGELES_COUNTY_CITIES
    )
    routable_cities = [
        city
        for city in (*LOS_ANGELES_COUNTY_CITIES, *requested_cities)
        if city not in NO_DRIVING_ROUTE_CITIES
    ]
    city_points: list[tuple[float, float]] = []
    for city in routable_cities:
        lookup = canonical_key(city.removeprefix("City of "))
        point = census_points.get(lookup)
        if point is None:
            point = city_center_from_public_geocoder(city)
        city_points.append(point)

    destination_names = [*routable_cities, *SPECIAL_DESTINATIONS]
    destination_points = [*city_points, *SPECIAL_DESTINATIONS.values()]
    lax_profiles = airport_profiles("LAX", destination_points)
    ont_profiles = airport_profiles("ONT", destination_points)

    profiles: dict[str, Any] = {}
    la_city_count = len([city for city in LOS_ANGELES_COUNTY_CITIES if city not in NO_DRIVING_ROUTE_CITIES])
    city_count = len(routable_cities)
    for index, destination in enumerate(destination_names):
        profiles[canonical_key(destination)] = {
            "destination": destination,
            "category": (
                "LA_COUNTY_CITY"
                if index < la_city_count
                else "REQUESTED_CALIFORNIA_CITY"
                if index < city_count
                else "SPECIAL_DESTINATION"
            ),
            "airports": {"LAX": lax_profiles[index], "ONT": ont_profiles[index]},
        }

    for city in NO_DRIVING_ROUTE_CITIES:
        profiles[canonical_key(city)] = {
            "destination": city,
            "category": "LA_COUNTY_CITY",
            "route_available": False,
            "manual_review_reason": "No drivable road connection from the mainland.",
            "airports": {},
        }

    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "coverage": "Los Angeles County cities, requested Southern California cities, and requested special destinations",
        "reference_route": "Rowland Heights city center → airport → destination center → Rowland Heights city center",
        "source": "Public city-center coordinates plus OpenStreetMap road routing. Refresh with Google Maps Routes before relying on a material fare change.",
        "profiles": profiles,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    archive = build_archive()
    args.output.write_text(json.dumps(archive, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(archive['profiles'])} destination profiles to {args.output}")


if __name__ == "__main__":
    main()
