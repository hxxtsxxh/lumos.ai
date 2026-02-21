"""Crime data loader for city, college, and county datasets.

Loads FBI UCR 2024 data from three pre-computed JSON lookups:
  - Table 8:  offensesByCity   → city_crime_lookup.json   (8,986 cities)
  - Table 9:  offensesByCollege → college_crime_lookup.json (676 universities)
  - Table 10: offensesByCounty → county_crime_lookup.json  (2,364 counties)

Resolution priority for a location:
  1. College match (if location name contains a university/college name)
  2. City match   (exact or fuzzy by city name + state)
  3. County match (by county name + state, as last-resort local data)
"""

import json
import logging
import os
from functools import lru_cache

logger = logging.getLogger("lumos.crime_data")

_BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "datasets")
_CITY_PATH = os.path.join(_BASE, "city_crime_lookup.json")
_COLLEGE_PATH = os.path.join(_BASE, "college_crime_lookup.json")
_COUNTY_PATH = os.path.join(_BASE, "county_crime_lookup.json")

# State abbreviation → full name
_STATE_ABBR: dict[str, str] = {
    "AL": "alabama", "AK": "alaska", "AZ": "arizona", "AR": "arkansas",
    "CA": "california", "CO": "colorado", "CT": "connecticut", "DE": "delaware",
    "DC": "district of columbia", "FL": "florida", "GA": "georgia", "HI": "hawaii",
    "ID": "idaho", "IL": "illinois", "IN": "indiana", "IA": "iowa",
    "KS": "kansas", "KY": "kentucky", "LA": "louisiana", "ME": "maine",
    "MD": "maryland", "MA": "massachusetts", "MI": "michigan", "MN": "minnesota",
    "MS": "mississippi", "MO": "missouri", "MT": "montana", "NE": "nebraska",
    "NV": "nevada", "NH": "new hampshire", "NJ": "new jersey", "NM": "new mexico",
    "NY": "new york", "NC": "north carolina", "ND": "north dakota", "OH": "ohio",
    "OK": "oklahoma", "OR": "oregon", "PA": "pennsylvania", "RI": "rhode island",
    "SC": "south carolina", "SD": "south dakota", "TN": "tennessee", "TX": "texas",
    "UT": "utah", "VT": "vermont", "VA": "virginia", "WA": "washington",
    "WV": "west virginia", "WI": "wisconsin", "WY": "wyoming",
}

# ── loaders (lazy, cached) ──────────────────────────────────────


def _load_json(path: str, label: str) -> dict:
    try:
        with open(path, "r") as f:
            data = json.load(f)
        logger.info(f"Loaded {label} crime lookup from {os.path.basename(path)}")
        return data
    except FileNotFoundError:
        logger.warning(f"{label} crime lookup not found: {path}")
        return {}
    except Exception as e:
        logger.warning(f"Failed to load {label} crime lookup: {e}")
        return {}


@lru_cache(maxsize=1)
def _city_lookup() -> dict:
    return _load_json(_CITY_PATH, "city")


@lru_cache(maxsize=1)
def _college_lookup() -> dict:
    return _load_json(_COLLEGE_PATH, "college")


@lru_cache(maxsize=1)
def _county_lookup() -> dict:
    return _load_json(_COUNTY_PATH, "county")


# ── normalisation helpers ────────────────────────────────────────


def _normalize_city(city: str) -> str:
    if not city:
        return ""
    name = city.split(",")[0].strip().lower()
    for suffix in [" city", " town", " village", " township", " borough", " cdp"]:
        if name.endswith(suffix):
            name = name[: -len(suffix)].strip()
    return name


def _state_name(abbr: str) -> str:
    return _STATE_ABBR.get(abbr.upper(), "") if abbr else ""


# ── public API ───────────────────────────────────────────────────


def get_college_crime_data(location: str) -> dict | None:
    """Match a location against the college crime dataset.

    Matches on university/college name substrings so that e.g.
    "Georgia Tech" matches "Georgia Institute of Technology".
    """
    lookup = _college_lookup()
    if not lookup:
        return None

    loc_lower = location.lower().strip() if location else ""
    if not loc_lower:
        return None

    # Direct key match
    if loc_lower in lookup:
        return lookup[loc_lower]

    # Substring match — check if any college key appears in the location
    # or if the location appears in a college key
    best = None
    best_len = 0
    for key, data in lookup.items():
        if key in loc_lower or loc_lower in key:
            if len(key) > best_len:
                best = data
                best_len = len(key)
        # Also check the formal university name stored in the entry
        uni_lower = data.get("university", "").lower()
        if uni_lower and (uni_lower in loc_lower or loc_lower in uni_lower):
            if len(uni_lower) > best_len:
                best = data
                best_len = len(uni_lower)

    return best


def get_city_crime_data(city_name: str, state_abbr: str = "") -> dict | None:
    """Look up per-city crime data from FBI UCR Table 8."""
    lookup = _city_lookup()
    if not lookup:
        return None

    city_key = _normalize_city(city_name)
    if not city_key:
        return None

    state_name = _state_name(state_abbr)

    # State-scoped search
    if state_name and state_name in lookup:
        state_cities = lookup[state_name]
        if city_key in state_cities:
            return state_cities[city_key]
        # Fuzzy
        for db_city, data in state_cities.items():
            if city_key in db_city or db_city in city_key:
                return data

    # Fallback: all states, prefer largest population
    best, best_pop = None, 0
    for sn, cities in lookup.items():
        if city_key in cities:
            pop = cities[city_key].get("population", 0)
            if pop > best_pop:
                best, best_pop = cities[city_key], pop
        else:
            for db_city, data in cities.items():
                if city_key in db_city or db_city in city_key:
                    pop = data.get("population", 0)
                    if pop > best_pop:
                        best, best_pop = data, pop

    return best


def get_county_crime_data(county_name: str, state_abbr: str = "") -> dict | None:
    """Look up per-county crime data from FBI UCR Table 10."""
    lookup = _county_lookup()
    if not lookup:
        return None

    county_key = county_name.lower().strip() if county_name else ""
    if not county_key:
        return None
    # Strip common suffixes
    for suffix in [" county", " parish", " borough"]:
        if county_key.endswith(suffix):
            county_key = county_key[: -len(suffix)].strip()

    state_name = _state_name(state_abbr)

    if state_name and state_name in lookup:
        if county_key in lookup[state_name]:
            return lookup[state_name][county_key]
        for db_county, data in lookup[state_name].items():
            if county_key in db_county or db_county in county_key:
                return data

    # Fallback: search all states
    for sn, counties in lookup.items():
        if county_key in counties:
            return counties[county_key]
        for db_county, data in counties.items():
            if county_key in db_county or db_county in county_key:
                return data

    return None


def _breakdown_from_data(data: dict) -> list[dict] | None:
    """Convert raw crime counts into a proportional breakdown list."""
    crime_types = [
        ("Larceny/Theft", data.get("larceny_theft", 0), "🔓"),
        ("Aggravated Assault", data.get("aggravated_assault", 0), "⚠️"),
        ("Burglary", data.get("burglary", 0), "🏠"),
        ("Motor Vehicle Theft", data.get("motor_vehicle_theft", 0), "🚗"),
        ("Robbery", data.get("robbery", 0), "💰"),
    ]
    total = sum(c for _, c, _ in crime_types) or 0
    if total == 0:
        return None

    result = []
    for name, count, icon in sorted(crime_types, key=lambda x: -x[1]):
        if count > 0:
            result.append({
                "type": name,
                "count": count,
                "proportion": round(count / total, 3),
                "icon": icon,
            })
    return result if result else None


def get_crime_breakdown(
    location: str,
    city_name: str = "",
    state_abbr: str = "",
    county: str = "",
) -> tuple[list[dict] | None, str]:
    """Unified crime breakdown with source attribution.

    Resolution order:
      1. College (if location matches a university name)
      2. City   (by city name + state)
      3. County (by county name + state)

    Returns (breakdown_list, source_label) or (None, "").
    """
    # 1 — College
    college = get_college_crime_data(location)
    if college:
        bd = _breakdown_from_data(college)
        if bd:
            uni_name = college.get("university", "College")
            logger.info(f"Crime breakdown from college data: {uni_name}")
            return bd, f"College: {uni_name}"

    # 2 — City
    city_data = get_city_crime_data(city_name or location, state_abbr)
    if city_data:
        bd = _breakdown_from_data(city_data)
        if bd:
            logger.info(f"Crime breakdown from city data: {city_name}")
            return bd, "FBI UCR City Data (2024)"

    # 3 — County
    county_data = get_county_crime_data(county or city_name or location, state_abbr)
    if county_data:
        bd = _breakdown_from_data(county_data)
        if bd:
            logger.info(f"Crime breakdown from county data: {county}")
            return bd, "FBI UCR County Data (2024)"

    return None, ""


def get_crime_rate_from_datasets(
    city_name: str, state_abbr: str = "", county: str = "",
) -> float | None:
    """Try to compute a per-100k crime rate from local datasets.

    Checks city data first (has population), then county (no population —
    returns total crime count for relative comparison only).
    """
    # City (has population → proper rate)
    city_data = get_city_crime_data(city_name, state_abbr)
    if city_data and city_data.get("population", 0) > 0:
        total = city_data.get("violent_crime", 0) + city_data.get("property_crime", 0)
        if total > 0:
            return (total / city_data["population"]) * 100_000

    # College (has enrollment → rate per student-100k)
    college = get_college_crime_data(city_name)
    if college and college.get("student_enrollment", 0) > 0:
        total = college.get("violent_crime", 0) + college.get("property_crime", 0)
        if total > 0:
            return (total / college["student_enrollment"]) * 100_000

    return None
