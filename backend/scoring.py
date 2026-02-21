"""Lumos Backend — Safety Scoring Logic"""

import json
import logging
import math
import numpy as np
from datetime import datetime, timedelta
from typing import Optional
from cachetools import LRUCache, cached
import threading

from config import ICON_MAP, CITY_NON_EMERGENCY, INTERNATIONAL_EMERGENCY, GEMINI_API_KEY
from models import IncidentType, TimeAnalysis, DataSource, HeatmapPoint, NearbyPOI
from nibrs_data import nibrs_stats
from city_crime_loader import get_crime_breakdown, get_crime_rate_from_datasets

# Setup logger
logger = logging.getLogger("lumos.scoring")

# ML LRU Cache (max 10,000 entries)
_ML_LRU_CACHE = LRUCache(maxsize=10000)
_ML_CACHE_LOCK = threading.Lock()

# ─────────────────────── NIBRS Offense Code → Human Name ─────────────────────
# FBI NIBRS offense codes mapped to concise human-readable crime types.
# Codes from: FBI Criminal Justice Information Services, NIBRS User Manual.
_NIBRS_CODE_TO_NAME: dict[str, str] = {
    "09A": "Murder",
    "09B": "Negligent Manslaughter",
    "09C": "Justifiable Homicide",
    "100": "Kidnapping",
    "11A": "Forcible Rape",
    "11B": "Forcible Sodomy",
    "11C": "Sexual Assault With Object",
    "11D": "Forcible Fondling",
    "120": "Robbery",
    "13A": "Aggravated Assault",
    "13B": "Simple Assault",
    "13C": "Intimidation",
    "200": "Arson",
    "210": "Extortion",
    "220": "Burglary",
    "23A": "Pocket-Picking",
    "23B": "Purse-Snatching",
    "23C": "Shoplifting",
    "23D": "Theft From Building",
    "23E": "Theft From Vehicle",
    "23F": "Theft of Vehicle Parts",
    "23G": "Theft (Other)",
    "23H": "Larceny/Theft",
    "240": "Motor Vehicle Theft",
    "250": "Counterfeiting/Forgery",
    "26A": "Fraud (False Pretense)",
    "26B": "Credit Card Fraud",
    "26C": "Impersonation",
    "26D": "Welfare Fraud",
    "26E": "Wire Fraud",
    "26F": "Identity Theft",
    "26G": "Hacking",
    "270": "Embezzlement",
    "280": "Stolen Property",
    "290": "Vandalism",
    "30A": "Drug Possession",
    "35A": "Drug Violation",
    "35B": "Drug Equipment Violation",
    "36A": "Illegal Gambling",
    "36B": "Gambling Equipment Violation",
    "370": "Pornography",
    "39A": "Betting/Wagering",
    "39B": "Operating Gambling House",
    "39C": "Sports Tampering",
    "40A": "Prostitution",
    "40B": "Assisting Prostitution",
    "40C": "Purchasing Prostitution",
    "49B": "Curfew Violation",
    "510": "Bribery",
    "520": "Weapon Law Violation",
    "526": "Weapon Offense",
    "61A": "Animal Cruelty",
    "64A": "Human Trafficking (Labor)",
    "64B": "Human Trafficking (Sex)",
    "720": "Disorderly Conduct",
}

# Temporal multipliers per crime category — how time-of-day shifts
# the expected proportion of each crime type. Derived from BJS
# "Criminal Victimization 2022" supplementary temporal tables.
#   night   = 10pm–5am   peak for violent/disorder
#   evening = 6pm–9pm    peak for assault, robbery
#   day     = 6am–5pm    peak for theft, fraud, shoplifting
_TEMPORAL_CRIME_MULTIPLIERS: dict[str, dict[str, float]] = {
    # Violent crimes spike at night
    "09A": {"night": 1.9, "evening": 1.3, "day": 0.5},
    "09B": {"night": 1.4, "evening": 1.1, "day": 0.7},
    "11A": {"night": 1.8, "evening": 1.3, "day": 0.5},
    "11B": {"night": 1.7, "evening": 1.2, "day": 0.6},
    "11C": {"night": 1.7, "evening": 1.2, "day": 0.6},
    "11D": {"night": 1.5, "evening": 1.2, "day": 0.7},
    "120": {"night": 1.7, "evening": 1.4, "day": 0.5},
    "13A": {"night": 1.6, "evening": 1.4, "day": 0.6},
    "13B": {"night": 1.3, "evening": 1.3, "day": 0.7},
    "13C": {"night": 1.2, "evening": 1.1, "day": 0.8},
    # Property crimes — day-heavy (opportunity)
    "220": {"night": 1.4, "evening": 0.9, "day": 0.8},
    "23A": {"night": 0.5, "evening": 1.1, "day": 1.2},
    "23B": {"night": 0.6, "evening": 1.2, "day": 1.1},
    "23C": {"night": 0.3, "evening": 0.9, "day": 1.4},
    "23D": {"night": 0.6, "evening": 0.9, "day": 1.2},
    "23E": {"night": 1.3, "evening": 1.0, "day": 0.8},
    "23F": {"night": 1.4, "evening": 1.0, "day": 0.7},
    "23G": {"night": 0.8, "evening": 1.0, "day": 1.1},
    "23H": {"night": 0.6, "evening": 1.0, "day": 1.2},
    "240": {"night": 1.5, "evening": 1.1, "day": 0.6},
    "290": {"night": 1.4, "evening": 1.1, "day": 0.7},
    # Fraud — business hours
    "250": {"night": 0.3, "evening": 0.7, "day": 1.5},
    "26A": {"night": 0.3, "evening": 0.6, "day": 1.5},
    "26B": {"night": 0.4, "evening": 0.7, "day": 1.4},
    "26C": {"night": 0.3, "evening": 0.6, "day": 1.5},
    "26F": {"night": 0.4, "evening": 0.7, "day": 1.3},
    "270": {"night": 0.2, "evening": 0.5, "day": 1.6},
    # Drugs — night/evening
    "30A": {"night": 1.4, "evening": 1.2, "day": 0.7},
    "35A": {"night": 1.5, "evening": 1.2, "day": 0.6},
    "35B": {"night": 1.3, "evening": 1.1, "day": 0.8},
    # Weapons — night
    "520": {"night": 1.6, "evening": 1.3, "day": 0.5},
    "526": {"night": 1.6, "evening": 1.3, "day": 0.5},
    # Disorder — night
    "720": {"night": 1.7, "evening": 1.3, "day": 0.5},
}

# Default temporal multiplier for codes not in the table
_DEFAULT_TEMPORAL = {"night": 1.0, "evening": 1.0, "day": 1.0}


def _get_time_period(hour: int) -> str:
    """Classify hour (0-23) into 'night', 'evening', or 'day'."""
    if hour >= 22 or hour < 6:
        return "night"
    elif hour >= 18:
        return "evening"
    return "day"


def predict_incident_types_nibrs(
    city_name: str,
    state_abbr: str,
    hour: int = 12,
    crime_rate_per_100k: float = 0.0,
) -> list[IncidentType] | None:
    """Predict incident type distribution using NIBRS agency offense_mix
    adjusted by temporal multipliers and XGBoost-derived crime level.

    Returns a ranked list of IncidentType objects, or None if no
    NIBRS agency data is available for the given city.

    ML processing:
    1. Retrieves the agency's historical offense_mix proportions (from
       XGBoost training data — same agency_profiles.json).
    2. Applies BJS-derived temporal multipliers based on hour-of-day
       to shift the distribution (e.g. theft ↑ during day, assault ↑ at night).
    3. Re-normalizes to a valid probability distribution.
    4. Maps NIBRS codes → human-readable names with icons.
    """
    agency = nibrs_stats.get_agency_profile(city_name, state_abbr) if city_name else None
    if not agency:
        return None

    offense_mix: dict[str, float] = agency.get("offense_mix", {})
    if not offense_mix:
        return None

    # Step 1: Apply temporal multipliers
    period = _get_time_period(hour)
    adjusted: dict[str, float] = {}
    for code, proportion in offense_mix.items():
        mult = _TEMPORAL_CRIME_MULTIPLIERS.get(code, _DEFAULT_TEMPORAL).get(period, 1.0)
        adjusted[code] = proportion * mult

    # Step 2: Re-normalize
    total = sum(adjusted.values()) or 1.0
    for code in adjusted:
        adjusted[code] /= total

    # Step 3: Aggregate by human-readable name (some codes map to same type)
    name_probs: dict[str, float] = {}
    for code, prob in adjusted.items():
        name = _NIBRS_CODE_TO_NAME.get(code, f"Other ({code})")
        name_probs[name] = name_probs.get(name, 0.0) + prob

    # Step 4: Sort descending, keep top 6 with probability >= 2%
    crime_level = _classify_crime_level(crime_rate_per_100k)
    sorted_types = sorted(name_probs.items(), key=lambda x: -x[1])

    result: list[IncidentType] = []
    for name, prob in sorted_types[:6]:
        if prob < 0.02:
            break
        result.append(IncidentType(
            type=name,
            probability=round(prob, 3),
            icon=get_icon(name),
            crimeLevel=crime_level,
        ))

    return result if result else None

# FBI mapping based roughly on UCR categories

# ─────────────────────────── City-level adjustment ──────────────

# BJS research: suburban and rural areas have substantially lower
# crime rates compared to urban centres.  When we only have a
# state-level rate, we estimate a local rate by classifying the
# Census tract population and applying a multiplier.
#
# Source: BJS "Criminal Victimization 2022", Table 5
#   Urban: ~1.3× state average
#   Suburban: ~0.55× state average
#   Rural: ~0.50× state average

def estimate_local_crime_rate(
    state_rate_per_100k: float,
    local_population: int,
    city_name: str = "",
    city_incidents: Optional[list] = None,
    total_annual_crime: int = 0,
    state_abbr: str = "",
) -> float:
    """Estimate a LOCAL crime rate using the best available data.

    Priority:
      1. **NIBRS agency-level data** (GA only) — real per-city crime rate
         computed from NIBRS per-agency incident counts.
      2. **FBI state rate × urban/suburban/rural multiplier** — heuristic
         adjustment based on city name and Census population.

    NOTE: We intentionally do NOT compute a rate from Socrata
    ``total_annual_crime`` because city open-data portals count ALL
    complaint types (harassment, traffic, lost property …) whereas
    FBI UCR rates only count Part I index crimes.  Mixing these two
    scales produces wildly inflated numbers (e.g. NYC ~29 000/100k
    vs FBI ~2 500/100k).  Socrata data is still used for incident
    type breakdown, heatmap, and hourly-risk curve.

    Returns estimated crime rate per 100k population.
    """
    # ── Priority 1: NIBRS agency-level data (all states) ──
    if nibrs_stats.loaded and nibrs_stats.agency_profiles:
        agency = nibrs_stats.get_agency_crime_rate(city_name)
        if agency and agency.get("rate_per_100k", 0) > 0:
            rate = agency["rate_per_100k"]
            logger.info(
                f"Using NIBRS agency Part I rate for {city_name}: "
                f"{rate:.0f}/100k ({agency['name']}, pop {agency['population']:,}, "
                f"Part I: {agency.get('annual_part1_incidents', '?')}/yr, "
                f"total: {agency['annual_avg_incidents']}/yr)"
            )
            return rate

    # ── Priority 2: FBI UCR per-city / per-college data ──
    ucr_rate = get_crime_rate_from_datasets(city_name, state_abbr)
    if ucr_rate is not None:
        logger.info(
            f"Using FBI UCR per-location rate for {city_name}: {ucr_rate:.0f}/100k"
        )
        return ucr_rate

    # ── Priority 3: State rate × local multiplier ──
    # Census API often returns COUNTY population, not city.
    # Use city name to detect if this is likely a well-known large city
    # versus a suburb/small city within a large county.
    city_lower = (city_name.split(",")[0].strip().lower() if city_name else "")

    # Known major US cities that ARE genuinely large urban cores
    _MAJOR_CITIES = {
        "new york", "los angeles", "chicago", "houston", "phoenix",
        "philadelphia", "san antonio", "san diego", "dallas", "san jose",
        "austin", "jacksonville", "fort worth", "columbus", "charlotte",
        "indianapolis", "san francisco", "seattle", "denver", "washington",
        "nashville", "oklahoma city", "el paso", "boston", "portland",
        "las vegas", "memphis", "louisville", "baltimore", "milwaukee",
        "albuquerque", "tucson", "fresno", "sacramento", "mesa",
        "kansas city", "atlanta", "omaha", "colorado springs", "raleigh",
        "long beach", "virginia beach", "miami", "oakland", "minneapolis",
        "tampa", "tulsa", "arlington", "new orleans", "detroit",
        "st. louis", "st louis", "cleveland", "pittsburgh", "cincinnati",
    }

    if city_lower in _MAJOR_CITIES:
        # This IS a major city — use urban core multiplier
        multiplier = 1.35
        area_type = "urban core"
    elif local_population >= 500_000:
        # Large county population but city name isn't a major city →
        # this is likely a suburb within a large county (e.g., Alpharetta in Fulton County)
        multiplier = 0.55
        area_type = "suburb (large county)"
    elif local_population >= 250_000:
        multiplier = 0.75
        area_type = "mid-size area"
    elif local_population >= 100_000:
        multiplier = 0.85
        area_type = "mid-size city"
    elif local_population >= 30_000:
        multiplier = 0.60
        area_type = "suburb/small city"
    elif local_population >= 10_000:
        multiplier = 0.45
        area_type = "suburb"
    else:
        multiplier = 0.40
        area_type = "rural/small town"

    adjusted = state_rate_per_100k * multiplier
    logger.info(
        f"Adjusted state rate {state_rate_per_100k:.0f}/100k → {adjusted:.0f}/100k "
        f"for {city_name} (pop {local_population:,}, {area_type}, ×{multiplier})"
    )
    return adjusted


def get_icon(crime_type: str) -> str:
    crime_lower = crime_type.lower()
    for keyword, icon in ICON_MAP.items():
        if keyword in crime_lower:
            return icon
    return "📌"





def compute_heatmap_from_incidents(incidents: list[dict], center_lat: float, center_lng: float,
                                   radius: float = 0.044, grid_size: int = 40,
                                   max_points: int = 2000) -> list[dict]:
    """Build a density-based heatmap from raw incidents.

    Divides the bounding box into a grid, counts incidents per cell,
    then emits one point per cell with weight proportional to density.
    radius ~0.044 deg ≈ 3 miles. Falls back to raw points if dataset is small.
    """
    from collections import defaultdict

    valid = []
    for inc in incidents:
        try:
            lat = float(inc.get("lat", 0))
            lng = float(inc.get("lng", 0))
            if lat == 0 or lng == 0:
                continue
            if abs(lat - center_lat) > radius or abs(lng - center_lng) > radius:
                continue
            raw_type = inc.get("type") or ""
            crime_type = str(raw_type).strip()
            if not crime_type or crime_type in ("0", "None", "Null", "N/A"):
                crime_type = "Unknown"
            elif crime_type.upper() in _NIBRS_CODE_TO_NAME:
                crime_type = _NIBRS_CODE_TO_NAME[crime_type.upper()]
            elif crime_type.isdigit() and len(crime_type) <= 2:
                crime_type = "Unknown"
            else:
                crime_type = crime_type.title()
            date_str = inc.get("date") or inc.get("incident_date")
            date_str = str(date_str).strip()[:19] if date_str else None
            source = inc.get("source", "")
            valid.append((lat, lng, crime_type, date_str, source))
        except (ValueError, TypeError):
            continue

    if not valid:
        return []

    # For small datasets, return raw points directly
    if len(valid) <= max_points:
        max_dist = radius * math.sqrt(2)
        points = []
        for lat, lng, ctype, date_str, source in valid:
            dist = math.sqrt((lat - center_lat) ** 2 + (lng - center_lng) ** 2)
            weight = max(0.15, 1.0 - dist / max_dist)
            pt = {"lat": lat, "lng": lng, "weight": round(weight, 3), "type": ctype, "source": source}
            if date_str:
                pt["date"] = date_str
            points.append(pt)
        return points

    # Grid-based density aggregation for large datasets
    import random
    cell_lat = (2 * radius) / grid_size
    cell_lng = (2 * radius) / grid_size

    grid: dict[tuple[int, int], list] = defaultdict(list)
    for lat, lng, ctype, date_str, source in valid:
        row = int((lat - (center_lat - radius)) / cell_lat)
        col = int((lng - (center_lng - radius)) / cell_lng)
        row = min(row, grid_size - 1)
        col = min(col, grid_size - 1)
        grid[(row, col)].append((lat, lng, ctype, date_str, source))

    if not grid:
        return []

    max_count = max(len(v) for v in grid.values())
    rng = random.Random(42)
    points = []
    for (row, col), cell_incidents in grid.items():
        count = len(cell_incidents)
        weight = max(0.05, count / max_count)

        # Use mean of actual incident positions instead of cell center,
        # with a small jitter to break any remaining grid artifacts
        mean_lat = sum(lat for lat, *_ in cell_incidents) / count
        mean_lng = sum(lng for _, lng, *_ in cell_incidents) / count
        jitter_lat = rng.gauss(0, cell_lat * 0.15)
        jitter_lng = rng.gauss(0, cell_lng * 0.15)
        pt_lat = mean_lat + jitter_lat
        pt_lng = mean_lng + jitter_lng

        type_counts: dict[str, int] = defaultdict(int)
        source_counts: dict[str, int] = defaultdict(int)
        dates: list[str] = []
        for _, _, ctype, date_str, source in cell_incidents:
            type_counts[ctype] += 1
            if source:
                source_counts[source] = source_counts.get(source, 0) + 1
            if date_str:
                dates.append(date_str)
        dominant_type = max(type_counts, key=type_counts.get)  # type: ignore[arg-type]
        dominant_source = max(source_counts, key=source_counts.get) if source_counts else ""  # type: ignore[arg-type]
        most_recent = max(dates) if dates else None

        pt = {
            "lat": round(pt_lat, 5),
            "lng": round(pt_lng, 5),
            "weight": round(weight, 3),
            "type": dominant_type,
            "source": dominant_source,
        }
        if most_recent:
            pt["date"] = most_recent
        points.append(pt)

    points.sort(key=lambda p: p["weight"], reverse=True)
    return points[:max_points]


def get_emergency_numbers(state_abbr: str, city: str, country_code: str = "US") -> list[dict]:
    """Return emergency numbers, supporting international locations."""
    country_info = INTERNATIONAL_EMERGENCY.get(country_code, INTERNATIONAL_EMERGENCY["DEFAULT"])

    numbers = [
        {"label": country_info["label"], "number": country_info["emergency"], "icon": "phone", "color": "danger"},
        {"label": "Crisis & Suicide Hotline", "number": "988", "icon": "hospital", "color": "safe"},
        {"label": "Domestic Violence", "number": "1-800-799-7233", "icon": "building", "color": "primary"},
    ]

    city_lower = city.lower() if city else ""
    non_emerg = "311"
    for key, num in CITY_NON_EMERGENCY.items():
        if key in city_lower:
            non_emerg = num
            break

    numbers.insert(1, {
        "label": "Non-Emergency Police",
        "number": non_emerg,
        "icon": "shield",
        "color": "caution",
    })

    return numbers


def _classify_crime_level(crime_rate_per_100k: float) -> str:
    """Classify the overall crime rate into a human-readable label.

    Buckets based on FBI UCR national averages:
      < 1500/100k  → Very Low
      1500-2500    → Low
      2500-3500    → Moderate
      3500-5000    → High
      > 5000       → Very High
    """
    if crime_rate_per_100k < 1500:
        return "Very Low"
    elif crime_rate_per_100k < 2500:
        return "Low"
    elif crime_rate_per_100k < 3500:
        return "Moderate"
    elif crime_rate_per_100k < 5000:
        return "High"
    else:
        return "Very High"


def classify_risk_from_score(safety_index: int) -> str:
    """Derive a contextual risk tag from the ML-computed safety index.

    This replaces the static crime-rate-only tag so the badge on the
    frontend matches the actual score the user sees.

    Mapping:
      >= 75  → Very Low
      60-74  → Low
      45-59  → Moderate
      30-44  → High
      < 30   → Very High
    """
    if safety_index >= 75:
        return "Very Low"
    elif safety_index >= 60:
        return "Low"
    elif safety_index >= 45:
        return "Moderate"
    elif safety_index >= 30:
        return "High"
    else:
        return "Very High"


def update_incident_crime_level(incident_types: list[IncidentType], safety_index: int) -> list[IncidentType]:
    """Update the crimeLevel on all incident types to match the final safety index."""
    level = classify_risk_from_score(safety_index)
    for it in incident_types:
        it.crimeLevel = level
    return incident_types


def build_incident_types(
    city_incidents: list[dict],
    fbi_data: dict,
    crime_rate_per_100k: float = 0.0,
    user_lat: float = 0.0,
    user_lng: float = 0.0,
    city_name: str = "",
    state_abbr: str = "",
    location: str = "",
    county: str = "",
    hour: int = 12,
) -> list[IncidentType]:
    """Build incident type distribution from real data.

    Priority:
      1.  Real city-level Socrata/ArcGIS incidents (proximity-weighted)
      1.5 NIBRS agency offense_mix (ML-adjusted by time-of-day)
      2.  FBI UCR datasets: college (676) → city (8,986) → county (2,364)
      3.  FBI state-level aggregate data
      4.  Hardcoded national averages (last resort)

    The returned IncidentType objects include a ``crimeLevel`` field
    (e.g. "Low") so the frontend can show context like
    "63% of LOW overall crime is larceny".
    """
    crime_level = _classify_crime_level(crime_rate_per_100k)
    incident_counts: dict[str, float] = {}
    _use_proximity = (user_lat != 0.0 and user_lng != 0.0)

    # ── Tier 1: Real city-level Socrata/ArcGIS incidents ──
    for inc in city_incidents:
        crime_type = str(inc.get("type", "Unknown")).strip()
        if crime_type and crime_type != "Unknown" and crime_type.lower() != "none":
            crime_type = crime_type.title()

            weight = 1.0
            if _use_proximity:
                try:
                    inc_lat = float(inc.get("lat") or 0)
                    inc_lng = float(inc.get("lng") or 0)
                    if inc_lat != 0 and inc_lng != 0:
                        dlat = (inc_lat - user_lat) * 111.0
                        dlng = (inc_lng - user_lng) * 85.0
                        dist_km = math.sqrt(dlat ** 2 + dlng ** 2)
                        weight = math.exp(-0.5 * (dist_km / 2.0) ** 2)
                        weight = max(weight, 0.05)
                except (ValueError, TypeError):
                    weight = 1.0

            incident_counts[crime_type] = incident_counts.get(crime_type, 0) + weight

    sorted_incidents = sorted(incident_counts.items(), key=lambda x: -x[1])
    total_incidents = sum(c for _, c in sorted_incidents) or 1

    incident_types = []
    for crime_type, count in sorted_incidents[:6]:
        prob = round(count / total_incidents, 3)
        if prob >= 0.02:
            incident_types.append(IncidentType(
                type=crime_type, probability=prob,
                icon=get_icon(crime_type), crimeLevel=crime_level,
            ))

    # ── Tier 1.5: NIBRS agency offense_mix (ML time-adjusted) ──
    if not incident_types:
        nibrs_types = predict_incident_types_nibrs(
            city_name=city_name,
            state_abbr=state_abbr,
            hour=hour,
            crime_rate_per_100k=crime_rate_per_100k,
        )
        if nibrs_types:
            logger.info(
                f"Using NIBRS offense_mix for '{city_name}' "
                f"(hour={hour}, {len(nibrs_types)} types)"
            )
            incident_types = nibrs_types

    # ── Tier 2: FBI UCR datasets (college → city → county) ──
    if not incident_types:
        ucr_breakdown, source = get_crime_breakdown(
            location=location or city_name,
            city_name=city_name,
            state_abbr=state_abbr,
            county=county,
        )
        if ucr_breakdown:
            logger.info(f"Using {source} breakdown for '{city_name or location}'")
            for item in ucr_breakdown:
                if item["proportion"] >= 0.02:
                    incident_types.append(IncidentType(
                        type=item["type"],
                        probability=item["proportion"],
                        icon=item["icon"],
                        crimeLevel=crime_level,
                    ))

    # ── Tier 3: FBI state-level aggregate data ──
    if not incident_types and fbi_data:
        fbi_incidents = [
            ("Larceny/Theft", fbi_data.get("larceny", 0), "🔓"),
            ("Aggravated Assault", fbi_data.get("aggravated_assault", 0), "⚠️"),
            ("Burglary", fbi_data.get("burglary", 0), "🏠"),
            ("Motor Vehicle Theft", fbi_data.get("motor_vehicle_theft", 0), "🚗"),
            ("Robbery", fbi_data.get("robbery", 0), "💰"),
        ]
        total_fbi = sum(c for _, c, _ in fbi_incidents) or 1
        for name, count, icon in fbi_incidents:
            if count > 0:
                incident_types.append(IncidentType(
                    type=name, probability=round(count / total_fbi, 3),
                    icon=icon, crimeLevel=crime_level,
                ))

    # ── Tier 4: Hardcoded national averages (last resort) ──
    if not incident_types:
        incident_types = [
            IncidentType(type="Theft", probability=0.40, icon="🔓", crimeLevel=crime_level),
            IncidentType(type="Assault", probability=0.22, icon="⚠️", crimeLevel=crime_level),
            IncidentType(type="Burglary", probability=0.20, icon="🏠", crimeLevel=crime_level),
            IncidentType(type="Vehicle Theft", probability=0.18, icon="🚗", crimeLevel=crime_level),
        ]

    return incident_types


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Citizen Incident Adjustment (CIA) — real-time scoring modifier
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _haversine_mi(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in miles (Haversine formula)."""
    R = 3958.8  # Earth radius in miles
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(dlng / 2) ** 2)
    # Clamp `a` to [0, 1] to guard against floating-point overshoot
    a = max(0.0, min(1.0, a))
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def compute_citizen_adjustment(
    target_lat: float,
    target_lng: float,
    citizen_incidents: list[dict],
    current_hour: int,
    target_hour: int | None = None,
) -> float:
    """Compute a safety-index *penalty* from nearby real-time Citizen incidents.

    Each incident contributes a weighted score based on:
      1. Distance decay     — closer incidents matter exponentially more
      2. Recency decay      — recent incidents matter more (half-life ≈ 2.8 h)
      3. Severity weight    — level + incidentScore + severity color
      4. Source credibility  — 911 dispatches > community reports
      5. Status filter      — closed/confirmed/good-news adjustments
      6. Forecast decay     — for future hours, current incidents fade

    Returns a non-negative float in [0, MAX_PENALTY] to *subtract* from
    the safety index.  Returns 0.0 when citizen_incidents is empty or all
    incidents are filtered out.
    """
    if not citizen_incidents:
        return 0.0

    import time as _time

    now_ms = _time.time() * 1000
    MAX_PENALTY = 25.0   # hard ceiling — CIA alone can't drop more than 25 pts
    SCALE = 12.0         # converts weighted-incident-sum → safety-index points

    total_weight = 0.0

    for inc in citizen_incidents:
        # ── Filter: skip good-news / non-crime incidents ──
        if inc.get("isGoodNews", False):
            continue

        i_lat = inc.get("lat")
        i_lng = inc.get("lng")
        if i_lat is None or i_lng is None:
            continue

        # ── 1. Distance decay ──
        # Half-weight at 0.3 mi, near-zero at 2 mi.
        # At 0.0 mi: 1.00 | 0.1 mi: 0.90 | 0.3 mi: 0.50
        # 0.5 mi: 0.26 | 1.0 mi: 0.08 | 2.0 mi: 0.02
        dist_mi = _haversine_mi(target_lat, target_lng, float(i_lat), float(i_lng))
        if dist_mi > 2.0:
            continue  # too far — skip entirely to save computation
        distance_w = 1.0 / (1.0 + (dist_mi / 0.3) ** 2)

        # ── 2. Recency decay ──
        # exp(-age_h / 4) → half-life ≈ 2.77 h
        # 0 h: 1.00 | 1 h: 0.78 | 3 h: 0.47 | 6 h: 0.22 | 12 h: 0.05
        ts = inc.get("ts", 0) or inc.get("cs", 0)
        if not ts or ts <= 0:
            continue  # no usable timestamp — skip to avoid false weighting
        age_hours = max(0.0, (now_ms - ts) / 3_600_000)
        if age_hours > 24.0:
            continue  # stale
        recency_w = math.exp(-age_hours / 4.0)

        # ── 3. Severity weight ──
        # Combine numeric level (0-2+) with incidentScore (0-~0.5).
        level = inc.get("level", 0)
        score = max(0.0, min(float(inc.get("incidentScore", 0) or 0), 1.0))
        sev_str = inc.get("severity", "grey")

        if level == 0 and sev_str == "green":
            severity_w = 0.10  # negligible (community events, etc.)
        elif level == 0:
            severity_w = 0.25  # minor (suspicious activity, noise)
        elif level == 1:
            severity_w = 0.50 + score * 0.50  # moderate (most crimes)
        else:  # level >= 2
            severity_w = 0.80 + score * 0.20  # serious (shooting, fire)
        severity_w = min(severity_w, 1.0)

        # ── 4. Source credibility ──
        source = inc.get("source", "unknown")
        if source == "911":
            source_w = 1.0    # highest confidence — police dispatch
        elif source == "community":
            source_w = 0.6    # user-reported, less verified
        else:
            source_w = 0.5    # unknown provenance

        # ── 5. Status filter ──
        closed = inc.get("closed", False)
        confirmed = inc.get("confirmed", False)

        if closed and age_hours > 3.0:
            status_w = 0.15   # resolved & old — mostly irrelevant
        elif closed:
            status_w = 0.40   # resolved recently — residual risk
        elif confirmed:
            status_w = 1.20   # verified active — boost
        else:
            status_w = 1.00   # unconfirmed but active

        # ── Combine per-incident weight ──
        incident_w = distance_w * recency_w * severity_w * source_w * status_w
        total_weight += incident_w

    # ── 6. Forecast decay for future/past hours ──
    # For the current-time query (target_hour is None), full weight applies.
    # For hourly-curve queries, decay linearly in circular-hour distance.
    forecast_w = 1.0
    if target_hour is not None:
        delta = abs(target_hour - current_hour)
        if delta > 12:
            delta = 24 - delta  # circular wrap (e.g. hour 1 vs 23 → 2 h apart)
        # exp(-delta / 6) → 0 h: 1.00 | 3 h: 0.61 | 6 h: 0.37 | 12 h: 0.14
        forecast_w = math.exp(-delta / 6.0)

    penalty = min(total_weight * SCALE * forecast_w, MAX_PENALTY)
    return penalty


def compute_safety_score(
    crime_rate_per_100k: float,
    hour: int,
    people_count: int,
    gender: str,
    weather_severity: float,
    population: int,
    city_incidents: list[dict],
    tf_model,
    duration_minutes: int = 60,
    state_abbr: str = "",
    crime_profile: Optional[dict] = None,
    is_college: float = 0.0,
    is_urban: float = 0.0,
    is_weekend: float = 0.0,
    poi_density: float = 0.0,
    lat: float = 0.0,
    lng: float = 0.0,
    live_events: int = 0,
    live_incidents: int = 0,
    moon_illumination: float = 0.5,
    city_name: str = "",
) -> tuple[int, float]:
    """Compute safety score via XGBoost inference on 25 NIBRS-derived features.

    Falls back to a formula-based score when the XGBoost model is not
    available (e.g. first run before training).
    Returns (safety_index, formula_score).
    """
    from datetime import datetime as _dt

    # ── Resolve NIBRS agency profile ──
    agency = nibrs_stats.get_agency_profile(city_name, state_abbr) if city_name else None

    # Temporal profile from NIBRS
    state_tp = nibrs_stats.state_profiles.get(state_abbr.upper(), {}) if state_abbr else {}

    # ── Pre-compute shared scalars ──
    time_sin = math.sin(2 * math.pi * hour / 24)
    time_cos = math.cos(2 * math.pi * hour / 24)

    gender_factor_val = {
        "female": 0.7, "male": 0.4, "mixed": 0.5, "prefer-not-to-say": 0.5,
    }.get(gender, 0.5)

    MAX_LIVE_EVENTS = 30
    MAX_LIVE_INCIDENTS = 50
    norm_live_events = min(live_events / MAX_LIVE_EVENTS, 1.0)
    norm_live_incidents = min(live_incidents / MAX_LIVE_INCIDENTS, 1.0)
    norm_people = min(people_count / 4, 1.0)

    # ── Build 25-feature vector (order MUST match FEATURE_NAMES in config) ──
    # Agency-level features (from pre-computed profiles)
    if agency:
        a_part1 = min(agency.get("part1_rate", 3000) / 8000, 1.0)
        a_violent = min(agency.get("violent_rate", 500) / 2000, 1.0)
        a_property = min(agency.get("property_rate", 2000) / 6000, 1.0)
        a_weapon = min(agency.get("weapon_rate", 0.15), 1.0)
        a_stranger = min(agency.get("stranger_rate", 0.35), 1.0)
        a_severity = min(agency.get("severity_score", 0.3), 1.0)
    else:
        # Fallback: derive from crime_rate_per_100k
        a_part1 = min(crime_rate_per_100k / 8000, 1.0)
        a_violent = min(crime_rate_per_100k * 0.2 / 2000, 1.0)
        a_property = min(crime_rate_per_100k * 0.7 / 6000, 1.0)
        a_weapon = 0.15
        a_stranger = 0.35
        a_severity = 0.3

    # State-level crime rate norm
    state_crime_norm = min(crime_rate_per_100k / 5000, 1.0)

    # Population group (BJS categories, normalized 0-1)
    if population >= 1_000_000:
        pop_group = 1.0
    elif population >= 500_000:
        pop_group = 0.85
    elif population >= 250_000:
        pop_group = 0.7
    elif population >= 100_000:
        pop_group = 0.55
    elif population >= 50_000:
        pop_group = 0.4
    elif population >= 10_000:
        pop_group = 0.25
    else:
        pop_group = 0.1

    # Temporal risk ratios from NIBRS state profiles
    hourly_dist = state_tp.get("hourly_dist", [])
    if hourly_dist and len(hourly_dist) == 24:
        avg_h = sum(hourly_dist) / 24 if sum(hourly_dist) > 0 else 1
        hourly_risk = min(hourly_dist[hour] / avg_h if avg_h > 0 else 1.0, 3.0) / 3.0
    else:
        # BJS fallback curve
        hourly_risk = 0.5 + 0.3 * math.sin(2 * math.pi * (hour - 6) / 24)
        hourly_risk = max(0.0, min(1.0, hourly_risk))

    dow_dist = state_tp.get("dow_dist", [])
    now_dow = _dt.now().weekday()
    if dow_dist and len(dow_dist) == 7:
        avg_d = sum(dow_dist) / 7 if sum(dow_dist) > 0 else 1
        dow_risk = min(dow_dist[now_dow] / avg_d if avg_d > 0 else 1.0, 2.0) / 2.0
    else:
        dow_risk = 0.55 if now_dow >= 5 else 0.45

    month_dist = state_tp.get("monthly_dist", [])
    now_month = _dt.now().month - 1
    if month_dist and len(month_dist) == 12:
        avg_m = sum(month_dist) / 12 if sum(month_dist) > 0 else 1
        monthly_risk = min(month_dist[now_month] / avg_m if avg_m > 0 else 1.0, 2.0) / 2.0
    else:
        monthly_risk = 0.5

    # Officer density (from agency profile if available)
    officer_density = 0.0
    if agency and agency.get("officer_count", 0) > 0 and agency.get("population", 0) > 0:
        officer_density = min(agency["officer_count"] / agency["population"] * 1000, 1.0)

    # Spatial density score (proxy from live incidents + poi density)
    spatial_density = min((norm_live_incidents * 0.6 + poi_density * 0.4), 1.0)

    # Assemble feature vector — 25 features, order matches FEATURE_NAMES / FEATURE_NAMES_V2
    features = np.array([[
        a_part1,              # agency_part1_rate
        a_violent,            # agency_violent_rate
        a_property,           # agency_property_rate
        a_weapon,             # agency_weapon_rate
        a_stranger,           # agency_stranger_rate
        a_severity,           # agency_severity_score
        state_crime_norm,     # state_crime_rate_norm
        pop_group,            # population_group
        hourly_risk,          # hourly_risk_ratio
        dow_risk,             # dow_risk_ratio
        monthly_risk,         # monthly_risk_ratio
        time_sin,             # time_sin
        time_cos,             # time_cos
        float(is_weekend),    # is_weekend
        norm_people,          # people_count_norm
        gender_factor_val,    # gender_factor
        weather_severity,     # weather_severity
        officer_density,      # officer_density
        float(is_college),    # is_college
        float(is_urban),      # is_urban
        poi_density,          # poi_density
        norm_live_events,     # live_events_norm
        norm_live_incidents,  # live_incidents_norm
        moon_illumination,    # moon_illumination
        spatial_density,      # spatial_density_score
    ]], dtype=np.float32)

    features = np.clip(features, 0.0, 1.0)

    # ━━━ ML Inference with Feature-Aware LRU Cache ━━━
    cache_key = (
        round(lat, 3), round(lng, 3), hour,
        round(a_part1, 2), round(weather_severity, 1),
        gender, people_count, int(is_weekend),
    )

    global _ML_LRU_CACHE, _ML_CACHE_LOCK
    with _ML_CACHE_LOCK:
        if cache_key in _ML_LRU_CACHE:
            prediction = _ML_LRU_CACHE[cache_key]
        else:
            prediction = float(tf_model.predict(features)[0][0])
            _ML_LRU_CACHE[cache_key] = prediction

    # ━━━ Formula fallback (used when XGBoost returns constant 0.65) ━━━
    crime_norm_f = crime_rate_per_100k / 5000
    crime_baseline = max(0.10, min(0.95, 1.0 / (1.0 + crime_norm_f ** 1.6)))
    time_raw = 0.5 + 0.5 * math.cos(2 * math.pi * ((hour - 3) % 24) / 24)
    time_factor = 1.10 - time_raw * 0.48
    group_factor = 1.0 + min(people_count - 1, 3) * 0.08
    is_night = 1 if (hour >= 18 or hour < 6) else 0
    night_mult = 1.2 if is_night else 1.0
    base_gp = {"female": 0.10, "male": 0.03, "mixed": 0.02}.get(gender, 0.02)
    gender_penalty = base_gp * night_mult
    gender_fac = 1.0 - gender_penalty
    weather_factor = 1.0 - weather_severity * 0.12
    duration_factor = 1.0 - min(duration_minutes / 60, 4) * 0.02

    formula_score = (
        crime_baseline * time_factor * group_factor * gender_fac
        * weather_factor * duration_factor
    )
    formula_score = max(0.05, min(0.95, formula_score))

    # Blend XGBoost (60%) with formula (40%) as guardrail.
    # Pure XGBoost when confident, formula smooths extreme predictions.
    if abs(prediction - 0.65) < 0.001 and agency is None:
        # Fallback model — use formula entirely
        blended = formula_score
    else:
        blended = prediction * 0.6 + formula_score * 0.4

    safety_index = int(np.clip(blended * 100, 5, 95))

    logger.info(
        f"Scoring: crime_rate={crime_rate_per_100k:.0f}/100k, "
        f"agency={'yes' if agency else 'no'}, xgb={prediction:.3f}, "
        f"formula={formula_score:.3f}, safety_index={safety_index}"
    )

    return safety_index, formula_score


def generate_synthetic_heatmap(
    lat: float, lng: float, safety_index: int, existing_points: list[dict],
    nearby_pois: list[dict] | None = None,
    incident_types: list[IncidentType] | None = None,
) -> list[dict]:
    """Fill in heatmap points using POI-based anchoring when real data is sparse.

    Instead of pure random Gaussian noise, clusters heatmap points around
    nearby POIs (bars, transit, parking, etc.) weighted by crime-type
    associations.  Falls back to center-based spread only if no POIs available.
    """
    if len(existing_points) >= 20:
        return existing_points

    rng = np.random.default_rng(abs(int(lat * 1000)) + abs(int(lng * 1000)))
    risk_factor = (100 - safety_index) / 100
    n_points = int(80 * risk_factor) + 15

    # POI types that attract crime, with relative weighting
    _POI_CRIME_WEIGHTS: dict[str, float] = {
        "bar": 1.5, "night_club": 1.6, "liquor_store": 1.3,
        "atm": 1.4, "bank": 0.8, "gas_station": 1.2,
        "convenience_store": 1.1, "parking": 1.3,
        "transit_station": 1.2, "bus_station": 1.1,
        "subway_station": 1.2, "train_station": 1.0,
        "shopping_mall": 0.9, "store": 0.7,
        "restaurant": 0.5, "park": 0.6,
    }

    # Build anchor points from POIs
    poi_anchors: list[dict] = []
    if nearby_pois:
        for poi in nearby_pois:
            poi_lat = poi.get("lat", poi.get("latitude", 0))
            poi_lng = poi.get("lng", poi.get("longitude", 0))
            if poi_lat and poi_lng:
                # Determine weight from POI type
                poi_type = str(poi.get("type", poi.get("category", ""))).lower()
                poi_name = str(poi.get("name", "")).lower()
                weight = 0.6  # default
                for key, w in _POI_CRIME_WEIGHTS.items():
                    if key in poi_type or key in poi_name:
                        weight = max(weight, w)
                        break
                poi_anchors.append({"lat": float(poi_lat), "lng": float(poi_lng), "weight": weight, "poi_type": poi_type})

    # Prepare crime types for sampling
    types_list = [it.type for it in incident_types] if incident_types else ["Theft", "Assault", "Burglary", "Vehicle Theft"]
    probs = [it.probability for it in incident_types] if incident_types else [0.4, 0.25, 0.2, 0.15]
    
    # Normalize probabilities to sum to 1.0 exactly
    total_prob = sum(probs)
    if total_prob > 0:
        probs = [p / total_prob for p in probs]
    else:
        probs = [1.0 / len(types_list)] * len(types_list)

    points = list(existing_points)
    for _ in range(n_points):
        if poi_anchors and rng.random() < 0.75:
            # 75% of points anchor around POIs
            anchor = poi_anchors[rng.integers(len(poi_anchors))]
            base_lat = anchor["lat"]
            base_lng = anchor["lng"]
            spread = 0.003 + rng.uniform(0, 0.003)
            base_weight = anchor["weight"]
        elif existing_points:
            # Cluster around existing real data points
            anchor = existing_points[rng.integers(len(existing_points))]
            base_lat = anchor["lat"]
            base_lng = anchor["lng"]
            spread = 0.004
            base_weight = 1.0
        else:
            # Fallback: spread around center
            base_lat = lat
            base_lng = lng
            spread = 0.008
            base_weight = 0.8

        offset_lat = rng.normal(0, spread)
        offset_lng = rng.normal(0, spread)
        weight = rng.uniform(0.15, 0.75) * risk_factor * base_weight
        
        # Sample a crime type
        c_type = rng.choice(types_list, p=probs)
        
        points.append({
            "lat": round(base_lat + offset_lat, 6),
            "lng": round(base_lng + offset_lng, 6),
            "weight": round(min(weight, 1.0), 3),
            "type": c_type,
        })

    return points


# ─────────────────────────── Gemini Heatmap Enrichment ──────────

_HEATMAP_GEMINI_CACHE = LRUCache(maxsize=64)
_HEATMAP_GEMINI_LOCK = threading.Lock()


async def gemini_enrich_heatmap(
    points: list[dict],
    *,
    city_name: str = "",
    state_abbr: str = "",
    crime_rate: float = 0.0,
    hour: int = 12,
    incident_types: list[IncidentType] | None = None,
    live_incident_summary: str = "",
) -> list[dict]:
    """Use Gemini to add contextual descriptions to heatmap points.

    Groups points by incident type, asks Gemini for a short analysis of each
    type in the context of this specific city/neighborhood, and attaches
    descriptions to every point.  Single API call, cached per city+hour.

    Falls back gracefully — points keep their original data if Gemini fails.
    """
    if not GEMINI_API_KEY or not points:
        return points

    # Build a set of unique incident types present in heatmap
    unique_types = list({p.get("type", "Unknown Incident") for p in points if p.get("type")})
    if not unique_types:
        return points

    cache_key = (city_name, state_abbr, round(crime_rate, -1), hour, tuple(sorted(unique_types)))
    with _HEATMAP_GEMINI_LOCK:
        if cache_key in _HEATMAP_GEMINI_CACHE:
            descriptions = _HEATMAP_GEMINI_CACHE[cache_key]
            for p in points:
                p_type = p.get("type", "Unknown Incident")
                if p_type in descriptions:
                    p["description"] = descriptions[p_type]
            return points

    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")

        crime_level = _classify_crime_level(crime_rate)
        time_label = "daytime" if 7 <= hour < 18 else "evening" if 18 <= hour < 22 else "late night"

        # Count occurrences of each type
        type_counts = {}
        for p in points:
            t = p.get("type", "Unknown Incident")
            type_counts[t] = type_counts.get(t, 0) + 1

        types_summary = ", ".join(f"{t} ({c} hotspots)" for t, c in sorted(type_counts.items(), key=lambda x: -x[1]))

        # Build a concentration summary to give Gemini local context
        total_pts = len(points)
        top_types = sorted(type_counts.items(), key=lambda x: -x[1])[:5]
        concentration = ", ".join(f"{t} ({c}/{total_pts}, {100*c//total_pts}%)" for t, c in top_types)

        live_context = f"\n- Recent live incidents (last 48h): {live_incident_summary}" if live_incident_summary else ""

        prompt = f"""For each incident type below, write ONE concise sentence (max 120 characters) describing where/when it typically occurs in this area. Reference well-known landmarks, campuses, districts, or transit hubs — NEVER mention specific street addresses.

City: {city_name or 'Unknown'}, {state_abbr or 'US'}
Crime level: {crime_level} ({crime_rate:.0f} per 100k)
Time: {hour}:00 ({time_label})
Breakdown: {concentration}{live_context}

Example format: "Common near university campuses and transit stations, especially after dark."

Return ONLY valid JSON mapping each type to its sentence:
{{{', '.join(f'"{t}": "sentence"' for t in unique_types)}}}"""

        result = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
            ),
        )
        text = result.text.strip()
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        if start_idx != -1 and end_idx != -1:
            text = text[start_idx:end_idx + 1]

        descriptions = json.loads(text)

        def _truncate(s: str, limit: int = 150) -> str:
            s = str(s).strip()
            if len(s) <= limit:
                return s
            truncated = s[:limit].rsplit(" ", 1)[0]
            return truncated.rstrip(".,;:") + "…"

        descriptions = {k: _truncate(v) for k, v in descriptions.items() if isinstance(v, str)}

        with _HEATMAP_GEMINI_LOCK:
            _HEATMAP_GEMINI_CACHE[cache_key] = descriptions

        for p in points:
            p_type = p.get("type", "Unknown Incident")
            if p_type in descriptions:
                p["description"] = descriptions[p_type]

        logger.info(f"Gemini heatmap enrichment: {len(descriptions)} types described for {city_name}")

    except Exception as e:
        logger.warning(f"Gemini heatmap enrichment failed (points unchanged): {e}")

    return points


# ─────────────────────────── Gemini Refinement Layer ────────────

# Light LRU cache for Gemini refinement (avoid re-calling for same context)
_GEMINI_CACHE = LRUCache(maxsize=128)
_GEMINI_CACHE_LOCK = threading.Lock()


async def gemini_refine_score(
    ml_score: int,
    *,
    city_name: str = "",
    state_abbr: str = "",
    hour: int = 12,
    crime_rate: float = 0.0,
    weather_condition: str = "Clear",
    weather_severity: float = 0.0,
    people_count: int = 1,
    gender: str = "prefer-not-to-say",
    incident_types: list[str] | None = None,
    is_route: bool = False,
) -> int:
    """Use Gemini to refine an ML safety score with contextual reasoning.

    The model receives the score + context and returns a JSON adjustment.
    Falls back to the original score on any failure so this is a best-effort
    enhancement that never degrades the pipeline.

    Returns the refined score (clamped to [5, 95]).
    """
    if not GEMINI_API_KEY:
        return ml_score

    cache_key = (
        ml_score, city_name, state_abbr, hour,
        round(crime_rate, -1), round(weather_severity, 1),
        people_count, gender, is_route,
    )
    with _GEMINI_CACHE_LOCK:
        if cache_key in _GEMINI_CACHE:
            return _GEMINI_CACHE[cache_key]

    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")

        risk_label = "safe" if ml_score >= 70 else "moderate risk" if ml_score >= 40 else "high risk"
        time_label = "daytime" if 7 <= hour < 18 else "evening" if 18 <= hour < 22 else "late night"
        incidents_str = ", ".join(incident_types[:5]) if incident_types else "none reported"

        prompt = f"""You are a public safety data analyst. An ML model scored this location's safety. Refine the score based on your knowledge.

Context:
- Location: {city_name or 'Unknown'}, {state_abbr or 'US'}
- ML Safety Score: {ml_score}/100 ({risk_label})
- Time: {hour}:00 ({time_label})
- Crime Rate: {crime_rate:.0f} per 100k
- Weather: {weather_condition}, severity {weather_severity:.1f}/1.0
- Group: {people_count} {'person' if people_count == 1 else 'people'}, {gender}
- Nearby incidents: {incidents_str}
- Analysis type: {"route segment" if is_route else "stationary location"}

Based on your knowledge of this area's actual safety reputation, recent crime trends, and the contextual factors above, provide a refined safety score.

Rules:
1. Your adjustment should be within ±15 points of the ML score
2. Only adjust significantly if you have strong knowledge about this specific area
3. Consider time-of-day effects, neighborhood reputation, and seasonal patterns
4. If unsure, return the original score

Return ONLY valid JSON (no markdown):
{{"refined_score": <int 5-95>, "reason": "1-sentence explanation"}}"""

        result = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
            ),
        )
        text = result.text.strip()

        # Parse response
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        if start_idx != -1 and end_idx != -1:
            text = text[start_idx:end_idx + 1]

        parsed = json.loads(text)
        refined = int(parsed.get("refined_score", ml_score))
        reason = parsed.get("reason", "")

        # Enforce ±15 bound
        refined = max(ml_score - 15, min(ml_score + 15, refined))
        refined = max(5, min(95, refined))

        if reason:
            logger.info(f"Gemini refinement: {ml_score} → {refined} ({reason})")

        with _GEMINI_CACHE_LOCK:
            _GEMINI_CACHE[cache_key] = refined
        return refined

    except Exception as e:
        logger.warning(f"Gemini refinement error (returning original score): {e}")
        return ml_score

