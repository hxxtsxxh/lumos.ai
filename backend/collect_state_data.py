"""Lumos — Collect & Save Real Crime Data for ML Training

Now reads from locally downloaded FBI CDE data (datasets/fbi_cde/) via
fbi_cde_loader.py, so no live API calls are needed for training data.

Usage:
    python collect_state_data.py          # Build from downloaded + hardcoded data
    python collect_state_data.py --quick  # Use hardcoded nationwide_data only

The ML model (ml_model.py) reads directly from fbi_cde_loader.py for training.
This script creates a supplementary training_data.json for backwards compatibility.
"""

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path

import numpy as np

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from config import DATA_GOV_API_KEY, FBI_CDE_BASE
from nationwide_data import STATE_CRIME_DATA, CITY_CRIME_DATA, compute_rates, REGIONAL_FACTORS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("lumos.collect")

# Output directory
CACHE_DIR = Path(__file__).resolve().parent.parent / "datasets" / "api_cache"
TRAINING_DATA_PATH = CACHE_DIR / "training_data.json"

# All US state abbreviations
ALL_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL",
    "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME",
    "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH",
    "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI",
    "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
]

# Correct CDE offense codes (not old slug names)
FBI_OFFENSES = ["V", "P", "HOM", "ROB", "ASS", "BUR", "LAR", "MVT"]

FIELD_MAP = {
    "V": "violent_crime", "P": "property_crime",
    "HOM": "homicide", "ROB": "robbery",
    "ASS": "aggravated_assault", "BUR": "burglary",
    "LAR": "larceny", "MVT": "motor_vehicle_theft",
}

# FBI SAPI for NIBRS detail (victim sex, weapons) — uses different API
FBI_SAPI_BASE = "https://api.usa.gov/crime/fbi/sapi/api"
NIBRS_OFFENSES = [
    "aggravated-assault", "robbery", "burglary",
    "larceny", "motor-vehicle-theft", "homicide",
]


async def fetch_state_fbi_cde(client, state: str, year: int = 2022) -> dict:
    """Fetch FBI CDE summarized data for a state and year.

    Uses correct CDE offense codes (V, P, HOM, etc.) not old slug names.
    """
    import httpx
    params = {"API_KEY": DATA_GOV_API_KEY, "from": f"01-{year}", "to": f"12-{year}"}
    result = {
        "state": state, "year": year, "source": "FBI_CDE_API",
        "violent_crime": 0, "property_crime": 0,
        "robbery": 0, "aggravated_assault": 0,
        "burglary": 0, "larceny": 0,
        "motor_vehicle_theft": 0, "homicide": 0,
        "population": 0,
    }

    try:
        tasks = [
            client.get(f"{FBI_CDE_BASE}/summarized/state/{state}/{o}", params=params)
            for o in FBI_OFFENSES
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        for offense, resp in zip(FBI_OFFENSES, responses):
            if isinstance(resp, Exception) or resp.status_code != 200:
                continue
            data = resp.json()
            actuals = data.get("offenses", {}).get("actuals", {})
            populations = data.get("populations", {}).get("population", {})

            for label, monthly in actuals.items():
                if "United States" not in label:
                    annual_total = sum(v for v in monthly.values() if isinstance(v, (int, float)))
                    field = FIELD_MAP.get(offense)
                    if field:
                        result[field] = int(annual_total)

            for label, monthly in populations.items():
                if "United States" not in label:
                    pop_values = [v for v in monthly.values() if isinstance(v, (int, float))]
                    if pop_values:
                        result["population"] = max(result["population"], int(pop_values[0]))

    except Exception as e:
        logger.warning(f"FBI CDE error for {state}/{year}: {e}")

    result["total_crime"] = result["violent_crime"] + result["property_crime"]
    return result


async def fetch_state_nibrs_victims(client, state: str) -> dict:
    """Fetch victim sex proportions from FBI SAPI."""
    male_total = 0
    female_total = 0

    try:
        tasks = [
            client.get(
                f"{FBI_SAPI_BASE}/nibrs/{offense}/victim/states/{state}/sex",
                params={"API_KEY": DATA_GOV_API_KEY},
            )
            for offense in NIBRS_OFFENSES
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        for resp in responses:
            if isinstance(resp, Exception) or resp.status_code != 200:
                continue
            data = resp.json()
            for entry in data.get("results", data.get("data", [])):
                sex_key = entry.get("key", entry.get("sex_code", ""))
                value = entry.get("value", 0)
                if isinstance(value, (int, float)):
                    if sex_key in ("M", "Male"):
                        male_total += int(value)
                    elif sex_key in ("F", "Female"):
                        female_total += int(value)

        total = male_total + female_total
        if total > 100:
            return {"M": round(male_total / total, 4), "F": round(female_total / total, 4)}
    except Exception as e:
        logger.debug(f"FBI SAPI victim sex unavailable for {state}: {e}")

    return {}


async def fetch_state_nibrs_weapons(client, state: str) -> float:
    """Fetch weapon involvement rate from FBI SAPI."""
    weapon_offenses = 0
    total_offenses = 0

    try:
        tasks = [
            client.get(
                f"{FBI_SAPI_BASE}/nibrs/{offense}/offense/states/{state}/weapons",
                params={"API_KEY": DATA_GOV_API_KEY},
            )
            for offense in NIBRS_OFFENSES
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        for resp in responses:
            if isinstance(resp, Exception) or resp.status_code != 200:
                continue
            data = resp.json()
            for entry in data.get("results", data.get("data", [])):
                weapon_name = entry.get("key", entry.get("weapon_name", "")).lower()
                value = entry.get("value", 0)
                if isinstance(value, (int, float)) and value > 0:
                    total_offenses += int(value)
                    if "personal" not in weapon_name and "unarmed" not in weapon_name:
                        weapon_offenses += int(value)

        if total_offenses > 100:
            return round(weapon_offenses / total_offenses, 4)
    except Exception as e:
        logger.debug(f"FBI SAPI weapons unavailable for {state}: {e}")

    return -1.0


async def fetch_state_historical(client, state: str) -> list[dict]:
    """Fetch multi-year crime data (2018-2022) for trend analysis."""
    years_data = []
    for year in range(2018, 2023):
        data = await fetch_state_fbi_cde(client, state, year)
        if data.get("total_crime", 0) > 0:
            years_data.append(data)
        await asyncio.sleep(0.1)  # Rate limit
    return years_data


async def collect_all_states(quick: bool = False) -> dict:
    """Collect comprehensive crime data for all states.
    
    If quick=True, only uses hardcoded data (no API calls).
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    all_data = {
        "collection_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "states": {},
        "cities": {},
        "metadata": {
            "sources": ["FBI UCR (hardcoded)", "FBI CDE API", "FBI SAPI NIBRS"],
            "total_states": 0,
            "total_cities": 0,
        }
    }

    # ── 1. Start with hardcoded state data (always available) ──
    logger.info("Loading hardcoded FBI UCR state data...")
    for abbr, data in STATE_CRIME_DATA.items():
        rates = compute_rates(data)
        total_crime = data.get("violent_crime", 0) + data.get("property_crime", 0)
        violent_ratio = data.get("violent_crime", 0) / max(total_crime, 1)
        murder_severity = data.get("murder", 0) / max(data.get("violent_crime", 1), 1)
        region = data.get("region", "Unknown")
        region_factors = REGIONAL_FACTORS.get(region, {"violent_mult": 1.0, "property_mult": 1.0})

        all_data["states"][abbr] = {
            "name": data["name"],
            "population": data["population"],
            "region": region,
            "violent_crime": data.get("violent_crime", 0),
            "property_crime": data.get("property_crime", 0),
            "murder": data.get("murder", 0),
            "robbery": data.get("robbery", 0),
            "aggravated_assault": data.get("aggravated_assault", 0),
            "burglary": data.get("burglary", 0),
            "larceny": data.get("larceny", 0),
            "motor_vehicle_theft": data.get("motor_vehicle_theft", 0),
            "source": "FBI_UCR_hardcoded",
            **rates,
            "violent_ratio": round(violent_ratio, 4),
            "murder_severity": round(murder_severity, 4),
            "regional_violent_mult": region_factors["violent_mult"],
            "regional_property_mult": region_factors["property_mult"],
        }

    # ── 2. Load hardcoded city data ──
    logger.info("Loading hardcoded FBI UCR city data...")
    for city_name, data in CITY_CRIME_DATA.items():
        rates = compute_rates(data)
        state_abbr = data.get("state", "")
        state_data = STATE_CRIME_DATA.get(state_abbr, {})
        total_crime = data.get("violent_crime", 0) + data.get("property_crime", 0)
        violent_ratio = data.get("violent_crime", 0) / max(total_crime, 1)
        murder_severity = data.get("murder", 0) / max(data.get("violent_crime", 1), 1)

        all_data["cities"][city_name] = {
            "state": state_abbr,
            "population": data["population"],
            "region": state_data.get("region", "Unknown"),
            "violent_crime": data.get("violent_crime", 0),
            "property_crime": data.get("property_crime", 0),
            "murder": data.get("murder", 0),
            "robbery": data.get("robbery", 0),
            "aggravated_assault": data.get("aggravated_assault", 0),
            "burglary": data.get("burglary", 0),
            "larceny": data.get("larceny", 0),
            "motor_vehicle_theft": data.get("motor_vehicle_theft", 0),
            "source": "FBI_UCR_hardcoded",
            **rates,
            "violent_ratio": round(violent_ratio, 4),
            "murder_severity": round(murder_severity, 4),
        }

    if not quick and DATA_GOV_API_KEY:
        # ── 3. Fetch FBI CDE API data for all states ──
        logger.info("Fetching FBI CDE API data for all states...")
        async with httpx.AsyncClient(timeout=20.0) as http_client:
            # Process states in batches to avoid rate limits
            batch_size = 5
            for i in range(0, len(ALL_STATES), batch_size):
                batch = ALL_STATES[i:i + batch_size]
                logger.info(f"  Batch {i // batch_size + 1}: {batch}")

                tasks = [fetch_state_fbi_cde(http_client, s) for s in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for state, result in zip(batch, results):
                    if isinstance(result, Exception):
                        logger.warning(f"  Failed {state}: {result}")
                        continue
                    if result.get("total_crime", 0) > 0:
                        # Merge API data (update rates)
                        rates = compute_rates(result)
                        total_crime = result.get("total_crime", 0)
                        violent_ratio = result.get("violent_crime", 0) / max(total_crime, 1)
                        murder_severity = result.get("homicide", 0) / max(result.get("violent_crime", 1), 1)

                        if state in all_data["states"]:
                            all_data["states"][state]["api_data"] = {
                                "year": result["year"],
                                "violent_crime": result["violent_crime"],
                                "property_crime": result["property_crime"],
                                "homicide": result["homicide"],
                                "robbery": result["robbery"],
                                "aggravated_assault": result["aggravated_assault"],
                                "burglary": result["burglary"],
                                "larceny": result["larceny"],
                                "motor_vehicle_theft": result["motor_vehicle_theft"],
                                "population": result["population"],
                                **rates,
                                "violent_ratio": round(violent_ratio, 4),
                                "murder_severity": round(murder_severity, 4),
                            }

                        # Save individual state file
                        state_file = CACHE_DIR / f"{state}_fbi_cde.json"
                        with open(state_file, "w") as f:
                            json.dump(result, f, indent=2)
                        logger.info(f"  Saved {state}: {total_crime} total crimes")

                await asyncio.sleep(0.5)  # Rate limit between batches

            # ── 4. Fetch NIBRS detail (victim sex + weapons) for all states ──
            logger.info("Fetching FBI SAPI NIBRS detail data...")
            for i in range(0, len(ALL_STATES), batch_size):
                batch = ALL_STATES[i:i + batch_size]
                logger.info(f"  NIBRS batch {i // batch_size + 1}: {batch}")

                victim_tasks = [fetch_state_nibrs_victims(http_client, s) for s in batch]
                weapon_tasks = [fetch_state_nibrs_weapons(http_client, s) for s in batch]
                
                victim_results = await asyncio.gather(*victim_tasks, return_exceptions=True)
                weapon_results = await asyncio.gather(*weapon_tasks, return_exceptions=True)

                for state, victims, weapons in zip(batch, victim_results, weapon_results):
                    nibrs_detail = {}
                    if not isinstance(victims, Exception) and victims:
                        nibrs_detail["victim_sex"] = victims
                    if not isinstance(weapons, Exception) and weapons >= 0:
                        nibrs_detail["weapon_rate"] = weapons

                    if nibrs_detail and state in all_data["states"]:
                        all_data["states"][state]["nibrs_detail"] = nibrs_detail

                        # Save individual NIBRS file
                        nibrs_file = CACHE_DIR / f"{state}_nibrs_detail.json"
                        with open(nibrs_file, "w") as f:
                            json.dump(nibrs_detail, f, indent=2)
                        logger.info(f"  NIBRS {state}: {nibrs_detail}")

                await asyncio.sleep(0.5)

            # ── 5. Fetch historical trends for all states ──
            logger.info("Fetching historical crime trends (2018-2022)...")
            for i in range(0, len(ALL_STATES), 3):
                batch = ALL_STATES[i:i + 3]
                logger.info(f"  Historical batch: {batch}")

                tasks = [fetch_state_historical(http_client, s) for s in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for state, result in zip(batch, results):
                    if isinstance(result, Exception) or not result:
                        continue
                    if state in all_data["states"]:
                        all_data["states"][state]["historical"] = result

                        hist_file = CACHE_DIR / f"{state}_historical.json"
                        with open(hist_file, "w") as f:
                            json.dump(result, f, indent=2, default=str)

                await asyncio.sleep(1.0)
    else:
        if quick:
            logger.info("Quick mode: skipping API calls, using hardcoded data only")
        elif not DATA_GOV_API_KEY:
            logger.warning("No DATA_GOV_API_KEY set — skipping API calls")

    # ── Update metadata ──
    all_data["metadata"]["total_states"] = len(all_data["states"])
    all_data["metadata"]["total_cities"] = len(all_data["cities"])

    # ── Save unified training data ──
    def _default_serializer(obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.float32, np.float64)):
            return float(obj)
        if isinstance(obj, (np.int32, np.int64)):
            return int(obj)
        return str(obj)

    with open(TRAINING_DATA_PATH, "w") as f:
        json.dump(all_data, f, indent=2, default=_default_serializer)

    logger.info(
        f"\nCollection complete!\n"
        f"  States: {all_data['metadata']['total_states']}\n"
        f"  Cities: {all_data['metadata']['total_cities']}\n"
        f"  Saved to: {TRAINING_DATA_PATH}\n"
    )

    return all_data


def ensure_training_data_exists() -> Path:
    """Ensure training data file exists. If not, create it with hardcoded data (quick mode).

    The ML model (ml_model.py) now reads directly from fbi_cde_loader.py for its
    primary training data. This function just ensures the supplementary cache file
    exists for backwards compatibility.

    Returns the path to the training data file.
    """
    if TRAINING_DATA_PATH.exists():
        # Check if file is reasonably fresh (less than 30 days old)
        age_days = (time.time() - os.path.getmtime(TRAINING_DATA_PATH)) / 86400
        if age_days < 30:
            logger.info(f"Using existing training data (age: {age_days:.1f} days)")
            return TRAINING_DATA_PATH
        logger.info(f"Training data is {age_days:.1f} days old — refreshing with hardcoded data")

    # Generate with quick mode (no API, just hardcoded data)
    logger.info("Generating training data from hardcoded nationwide data...")
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're already in an async context, schedule it
            asyncio.ensure_future(collect_all_states(quick=True))
        else:
            loop.run_until_complete(collect_all_states(quick=True))
    except RuntimeError:
        asyncio.run(collect_all_states(quick=True))
    return TRAINING_DATA_PATH


def load_training_data() -> dict:
    """Load the saved training data. Creates it if it doesn't exist."""
    path = ensure_training_data_exists()
    with open(path, "r") as f:
        return json.load(f)


if __name__ == "__main__":
    quick = "--quick" in sys.argv
    asyncio.run(collect_all_states(quick=quick))
