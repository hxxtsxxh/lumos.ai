"""Lumos Backend — FBI CDE Data Loader

Reads downloaded FBI CDE data from datasets/fbi_cde/ and returns
structured dicts for use by the ML model, data fetchers, and scoring.

Data downloaded by download_fbi_data.py is stored as per-state JSON files
under datasets/fbi_cde/{endpoint_type}/{state}.json.
"""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("lumos.loader")

_FBI_CDE_DIR = Path(__file__).resolve().parent.parent / "datasets" / "fbi_cde"

# CDE summarized codes → human-readable field names used by the rest of the app
_SUMMARIZED_FIELD_MAP = {
    "V":   "violent_crime",
    "P":   "property_crime",
    "HOM": "homicide",
    "RPE": "rape",
    "ROB": "robbery",
    "ASS": "aggravated_assault",
    "BUR": "burglary",
    "LAR": "larceny",
    "MVT": "motor_vehicle_theft",
    "ARS": "arson",
}


def _extract_annual_totals(offense_data: dict, year: Optional[int] = None) -> tuple[int, int]:
    """Extract annual total offenses and population from a CDE offense response.

    Args:
        offense_data: Response from /summarized/state/{state}/{code}
        year: If set, only sum months for that year.  Otherwise sum all months.

    Returns:
        (total_offenses, population)
    """
    total_offenses = 0
    population = 0

    actuals = offense_data.get("offenses", {}).get("actuals", {})
    for label, monthly in actuals.items():
        if "United States" in label:
            continue
        for month_key, val in monthly.items():
            if not isinstance(val, (int, float)):
                continue
            if year is not None:
                # month_key format is "mm-yyyy"
                parts = month_key.split("-")
                if len(parts) == 2 and parts[1] != str(year):
                    continue
            total_offenses += int(val)

    pops = offense_data.get("populations", {}).get("population", {})
    for label, monthly in pops.items():
        if "United States" in label:
            continue
        vals = [v for v in monthly.values() if isinstance(v, (int, float))]
        if vals:
            population = max(population, int(vals[0]))

    return total_offenses, population


def load_state_summarized(state_abbr: str, year: Optional[int] = None) -> dict:
    """Load summarized crime data for a state from the downloaded cache.

    When *year* is ``None`` (the default) the **most recent single year**
    available in the data is returned — NOT the sum of all years.  This
    prevents inflating the crime totals by 5-6× (the old bug).

    Returns dict with keys like 'violent_crime', 'property_crime', 'homicide',
    'population', 'source', 'year' — matching the format expected by
    data_fetchers.fetch_fbi_crime_data() callers.
    """
    fpath = _FBI_CDE_DIR / "summarized" / f"{state_abbr}.json"
    if not fpath.exists():
        return {}

    # When no year is specified, find the latest available year first.
    if year is None:
        all_years = load_state_summarized_all_years(state_abbr)
        if all_years:
            latest_year = max(all_years.keys())
            result = all_years[latest_year]
            result["source"] = "FBI CDE (cached)"
            result["record_count"] = result.get("violent_crime", 0) + result.get("property_crime", 0)
            return result

    try:
        with open(fpath) as f:
            data = json.load(f)
    except Exception as e:
        logger.warning(f"Could not load summarized/{state_abbr}.json: {e}")
        return {}

    result = {
        "source": "FBI CDE (cached)",
        "year": year or 2023,
        "violent_crime": 0, "property_crime": 0,
        "robbery": 0, "aggravated_assault": 0,
        "burglary": 0, "larceny": 0,
        "motor_vehicle_theft": 0, "homicide": 0,
        "rape": 0, "arson": 0,
        "population": 0, "record_count": 0,
    }

    for code, field in _SUMMARIZED_FIELD_MAP.items():
        if code not in data:
            continue
        offenses, pop = _extract_annual_totals(data[code], year)
        result[field] = offenses
        if pop > result["population"]:
            result["population"] = pop

    result["record_count"] = result["violent_crime"] + result["property_crime"]
    return result


def load_state_summarized_all_years(state_abbr: str) -> dict[int, dict]:
    """Load per-year summarized totals for a state (2018-2023).

    Returns {year: {field: value, ...}, ...}
    """
    fpath = _FBI_CDE_DIR / "summarized" / f"{state_abbr}.json"
    if not fpath.exists():
        return {}

    try:
        with open(fpath) as f:
            data = json.load(f)
    except Exception:
        return {}

    # Discover available years from the V (violent crime) data's monthly keys
    available_years = set()
    v_data = data.get("V", {})
    actuals = v_data.get("offenses", {}).get("actuals", {})
    for label, monthly in actuals.items():
        for month_key in monthly:
            parts = month_key.split("-")
            if len(parts) == 2:
                try:
                    available_years.add(int(parts[1]))
                except ValueError:
                    pass

    results = {}
    for yr in sorted(available_years):
        yr_data = {
            "year": yr,
            "violent_crime": 0, "property_crime": 0,
            "homicide": 0, "rape": 0, "robbery": 0,
            "aggravated_assault": 0, "burglary": 0, "larceny": 0,
            "motor_vehicle_theft": 0, "arson": 0,
            "population": 0,
        }

        for code, field in _SUMMARIZED_FIELD_MAP.items():
            if code not in data:
                continue
            offenses, pop = _extract_annual_totals(data[code], yr)
            yr_data[field] = offenses
            if pop > yr_data["population"]:
                yr_data["population"] = pop

        if yr_data["violent_crime"] + yr_data["property_crime"] > 0:
            results[yr] = yr_data

    return results


def load_state_historical(state_abbr: str) -> list[dict]:
    """Load historical crime trends for a state (for the /api/historical endpoint).

    Returns list of dicts sorted by year, each containing:
      year, violentCrime, propertyCrime, total, population, ratePerCapita
    """
    all_years = load_state_summarized_all_years(state_abbr)
    if not all_years:
        return []

    result = []
    for yr, d in sorted(all_years.items()):
        pop = d.get("population", 0)
        vc = d.get("violent_crime", 0)
        pc = d.get("property_crime", 0)
        total = vc + pc
        rate = (total / pop * 100_000) if pop > 0 else 0

        result.append({
            "year": yr,
            "violentCrime": vc,
            "propertyCrime": pc,
            "total": total,
            "population": pop,
            "ratePerCapita": round(rate, 1),
        })

    return result


def load_state_pe(state_abbr: str) -> dict:
    """Load law enforcement employee data for a state."""
    fpath = _FBI_CDE_DIR / "pe" / f"{state_abbr}.json"
    if not fpath.exists():
        return {}

    try:
        with open(fpath) as f:
            data = json.load(f)
    except Exception:
        return {}

    # Extract officer counts
    result = {"officers_per_1000": 0.0, "total_officers": 0}
    rates = data.get("rates", {})
    for label, monthly in rates.items():
        if "Officers per" in label:
            vals = [v for v in monthly.values() if isinstance(v, (int, float))]
            if vals:
                result["officers_per_1000"] = round(sum(vals) / len(vals), 2)

    actuals = data.get("actuals", {})
    for label, monthly in actuals.items():
        if "Male Officers" in label or "Female Officers" in label:
            vals = [v for v in monthly.values() if isinstance(v, (int, float))]
            if vals:
                result["total_officers"] += int(vals[-1])  # Most recent year

    return result


def load_state_arrest(state_abbr: str) -> dict:
    """Load arrest data for a state. Returns {code: total_count, ...}."""
    fpath = _FBI_CDE_DIR / "arrest" / f"{state_abbr}.json"
    if not fpath.exists():
        return {}

    try:
        with open(fpath) as f:
            data = json.load(f)
    except Exception:
        return {}

    results = {}
    for code, offense_data in data.items():
        if not isinstance(offense_data, dict):
            continue
        actuals = offense_data.get("actuals", {})
        total = 0
        for label, monthly in actuals.items():
            if "United States" in label:
                continue
            total += sum(v for v in monthly.values() if isinstance(v, (int, float)))
        results[code] = total

    return results


def load_all_states_summarized(year: Optional[int] = None) -> dict[str, dict]:
    """Load summarized data for all available states.

    Returns {state_abbr: {field: value, ...}, ...}
    """
    summ_dir = _FBI_CDE_DIR / "summarized"
    if not summ_dir.exists():
        return {}

    results = {}
    for fpath in sorted(summ_dir.glob("*.json")):
        state = fpath.stem
        if state == "national":
            continue
        data = load_state_summarized(state, year)
        if data and data.get("population", 0) > 0:
            results[state] = data

    return results


def load_all_states_with_details(year: Optional[int] = None) -> dict[str, dict]:
    """Load comprehensive data for all states: summarized + PE + arrest.

    Returns enriched records suitable for ML training.
    """
    states = load_all_states_summarized(year)

    for abbr in list(states.keys()):
        # Add PE data
        pe = load_state_pe(abbr)
        if pe:
            states[abbr]["officers_per_1000"] = pe.get("officers_per_1000", 0)
            states[abbr]["total_officers"] = pe.get("total_officers", 0)

        # Add arrest totals
        arrests = load_state_arrest(abbr)
        if arrests:
            states[abbr]["total_arrests"] = arrests.get("all", 0)
            states[abbr]["drug_arrests"] = arrests.get("150", 0)
            states[abbr]["dui_arrests"] = arrests.get("260", 0)

        # Compute derived rates
        pop = states[abbr].get("population", 0)
        if pop > 0:
            vc = states[abbr].get("violent_crime", 0)
            pc = states[abbr].get("property_crime", 0)
            total = vc + pc
            states[abbr]["violent_rate"] = round(vc / pop * 100_000, 1)
            states[abbr]["property_rate"] = round(pc / pop * 100_000, 1)
            states[abbr]["total_rate"] = round(total / pop * 100_000, 1)
            states[abbr]["murder_rate"] = round(states[abbr].get("homicide", 0) / pop * 100_000, 2)
            states[abbr]["robbery_rate"] = round(states[abbr].get("robbery", 0) / pop * 100_000, 1)
            states[abbr]["assault_rate"] = round(states[abbr].get("aggravated_assault", 0) / pop * 100_000, 1)
            states[abbr]["burglary_rate"] = round(states[abbr].get("burglary", 0) / pop * 100_000, 1)
            states[abbr]["larceny_rate"] = round(states[abbr].get("larceny", 0) / pop * 100_000, 1)
            states[abbr]["mvt_rate"] = round(states[abbr].get("motor_vehicle_theft", 0) / pop * 100_000, 1)
            states[abbr]["violent_ratio"] = round(vc / max(total, 1), 4)
            states[abbr]["murder_severity"] = round(
                states[abbr].get("homicide", 0) / max(vc, 1), 4
            )

    return states
