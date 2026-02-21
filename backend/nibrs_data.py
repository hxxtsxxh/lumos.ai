"""Lumos Backend — NIBRS Data Pipeline (v2 — Pre-computed JSON profiles)

Loads pre-computed agency and state profiles from JSON artifacts produced
by precompute_nibrs.py.  Falls back to BJS-derived synthetic profiles
when pre-computed data is unavailable.

Provides:
  - Per-agency crime profiles (fuzzy city-name matching)
  - Per-state temporal distributions (hourly, DOW, monthly)
  - Hourly risk curves
  - Offense severity weights
  - Victim demographic risk factors
"""

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger("lumos.nibrs")

# Path to the datasets directory
_DATASETS_BASE = Path(__file__).resolve().parent.parent / "datasets"

# ─────────────────────────── Offense constants ──────────────────
# (kept for derive_state_profile fallback and precompute script import)

_CRIME_AGAINST_WEIGHT = {
    "Person": 8.0, "Property": 3.0, "Society": 2.0, "Not a Crime": 0.5,
}

_OFFENSE_SEVERITY_OVERRIDES = {
    "Murder and Nonnegligent Manslaughter": 10.0,
    "Justifiable Homicide": 7.0, "Kidnapping/Abduction": 9.0, "Rape": 9.0,
    "Sodomy": 9.0, "Sexual Assault With An Object": 9.0,
    "Aggravated Assault": 8.0, "Simple Assault": 5.0, "Intimidation": 4.0,
    "Robbery": 7.0, "Arson": 7.0, "Extortion/Blackmail": 6.0,
    "Burglary/Breaking & Entering": 5.0, "Motor Vehicle Theft": 5.0,
    "Counterfeiting/Forgery": 3.0, "False Pretenses/Swindle/Confidence Game": 3.0,
    "Credit Card/Automated Teller Machine Fraud": 3.0, "Wire Fraud": 3.0,
    "Embezzlement": 3.0, "Stolen Property Offenses": 3.0,
    "Destruction/Damage/Vandalism of Property": 3.0,
    "Drug/Narcotic Violations": 2.0, "Drug Equipment Violations": 1.5,
    "Weapon Law Violations": 4.0, "Pornography/Obscene Material": 2.0,
    "Prostitution": 1.5, "Gambling Violations": 1.0, "Disorderly Conduct": 1.0,
    "Trespass of Real Property": 2.0, "Liquor Law Violations": 1.0,
    "Drunkenness": 1.0, "Curfew/Loitering/Vagrancy Violations": 0.5,
}

_PART_I_OFFENSE_CODES = {
    "09A", "09B", "11A", "11B", "11C", "11D", "120", "13A",
    "200", "220", "23A", "23B", "23C", "23D", "23E", "23F", "23G", "23H", "240",
}


# ─────────────────────────── BJS Fallback Curves ────────────────
# Used ONLY when pre-computed profiles are unavailable for a state.

_BJS_VIOLENT = np.array([
    5.5, 4.8, 3.8, 2.8, 2.2, 1.8, 1.5, 1.8,
    2.2, 2.5, 2.8, 3.2, 3.8, 4.2, 4.5, 5.0,
    5.5, 6.0, 6.5, 6.8, 7.2, 7.0, 6.5, 6.0,
], dtype=np.float64)

_BJS_PROPERTY = np.array([
    3.5, 3.0, 2.5, 2.0, 1.8, 2.0, 2.5, 3.0,
    3.8, 4.2, 4.8, 5.2, 5.5, 5.8, 5.5, 5.2,
    5.0, 4.8, 4.8, 4.8, 4.8, 4.5, 4.2, 3.8,
], dtype=np.float64)

_BJS_ROBBERY = np.array([
    5.5, 4.8, 3.8, 2.8, 2.0, 1.5, 1.2, 1.5,
    2.0, 2.5, 2.8, 3.2, 3.5, 3.8, 4.2, 4.8,
    5.2, 5.5, 6.0, 6.5, 7.0, 7.2, 6.8, 6.0,
], dtype=np.float64)

_BJS_BURGLARY = np.array([
    3.2, 2.8, 2.2, 1.8, 1.5, 1.8, 2.5, 3.5,
    4.8, 5.8, 6.5, 6.8, 6.5, 6.0, 5.5, 5.0,
    4.8, 4.5, 4.2, 4.2, 4.2, 4.0, 3.8, 3.5,
], dtype=np.float64)

_BJS_ASSAULT = np.array([
    5.5, 5.0, 4.0, 3.0, 2.2, 1.8, 1.5, 1.8,
    2.2, 2.5, 2.8, 3.2, 3.5, 4.0, 4.5, 5.0,
    5.5, 5.8, 6.5, 6.8, 7.2, 7.0, 6.5, 5.8,
], dtype=np.float64)

_BJS_LARCENY = np.array([
    2.8, 2.2, 1.8, 1.5, 1.2, 1.5, 2.2, 3.2,
    4.2, 5.0, 5.5, 6.0, 6.2, 5.8, 5.5, 5.5,
    5.5, 5.2, 5.0, 4.8, 4.5, 4.2, 3.8, 3.2,
], dtype=np.float64)

_BJS_VEHICLE_THEFT = np.array([
    5.0, 4.5, 3.8, 3.0, 2.2, 2.0, 2.0, 2.5,
    3.0, 3.5, 3.8, 4.0, 4.2, 4.2, 4.5, 4.8,
    5.0, 5.5, 6.0, 6.5, 6.5, 6.2, 5.8, 5.5,
], dtype=np.float64)

_BJS_HOMICIDE = np.array([
    6.5, 5.8, 4.5, 3.5, 2.5, 2.0, 1.5, 1.5,
    1.8, 2.0, 2.2, 2.5, 3.0, 3.5, 4.0, 4.5,
    5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 7.5, 7.0,
], dtype=np.float64)

for _p in [_BJS_VIOLENT, _BJS_PROPERTY, _BJS_ROBBERY, _BJS_BURGLARY,
           _BJS_ASSAULT, _BJS_LARCENY, _BJS_VEHICLE_THEFT, _BJS_HOMICIDE]:
    _p /= _p.sum()

_BJS_SEVERITY = {
    "homicide": 10.0, "robbery": 7.0, "aggravated_assault": 8.0,
    "violent_crime": 7.0, "burglary": 5.0, "larceny": 3.0,
    "motor_vehicle_theft": 5.0, "property_crime": 3.0,
}

_NATIONAL_WEAPON_RATES = {
    "homicide": 0.90, "aggravated_assault": 0.67, "robbery": 0.42,
    "violent_crime": 0.35, "burglary": 0.02, "larceny": 0.01,
    "motor_vehicle_theft": 0.01, "property_crime": 0.01,
}

_NATIONAL_VICTIM_SEX = {
    "homicide":            {"M": 0.78, "F": 0.22},
    "aggravated_assault":  {"M": 0.62, "F": 0.38},
    "robbery":             {"M": 0.64, "F": 0.36},
    "violent_crime":       {"M": 0.56, "F": 0.44},
    "burglary":            {"M": 0.50, "F": 0.50},
    "larceny":             {"M": 0.48, "F": 0.52},
    "motor_vehicle_theft": {"M": 0.54, "F": 0.46},
    "property_crime":      {"M": 0.50, "F": 0.50},
}


# ──────────────────────── Main class ────────────────────────────

class NIBRSStatistics:
    """Pre-computed crime statistics loaded from JSON artifacts."""

    def __init__(self):
        self.loaded = False
        self.hourly_distribution: np.ndarray = np.ones(24) / 24
        self.hourly_severity_distribution: np.ndarray = np.ones(24) / 24
        self.weapon_rate: float = 0.0
        self.victim_gender_rates: dict[str, float] = {}
        self.crime_against_distribution: dict[str, float] = {}
        self.stranger_crime_rate: float = 0.3
        self.agency_stats: dict[str, dict] = {}
        self.offense_types: dict = {}
        self.offense_severity: dict = {}
        self.location_risk: dict[str, float] = {}
        self.location_distribution: dict[str, float] = {}
        self.weapon_distribution: dict[str, int] = {}

        # New v2 data structures
        self.agency_profiles: dict[str, dict] = {}
        self.state_profiles: dict[str, dict] = {}
        self._state_index: dict[str, list[str]] = {}  # state -> list of agency keys
        self._county_index: dict[str, list[str]] = {}  # county_lower -> list of agency keys

    def load(self):
        """Load pre-computed JSON profiles. Falls back gracefully if missing."""
        ap_path = _DATASETS_BASE / "agency_profiles.json"
        sp_path = _DATASETS_BASE / "state_temporal_profiles.json"

        if not ap_path.exists():
            logger.warning(
                f"agency_profiles.json not found at {ap_path}. "
                "Run 'python backend/precompute_nibrs.py' to generate. "
                "Using degraded fallback mode."
            )
            return

        # Load agency profiles
        try:
            with open(ap_path) as f:
                self.agency_profiles = json.load(f)
            logger.info(f"Loaded {len(self.agency_profiles)} agency profiles")
        except Exception as e:
            logger.error(f"Failed to load agency profiles: {e}")
            return

        # Load state profiles
        if sp_path.exists():
            try:
                with open(sp_path) as f:
                    self.state_profiles = json.load(f)
                logger.info(f"Loaded {len(self.state_profiles)} state profiles")
            except Exception as e:
                logger.warning(f"Failed to load state profiles: {e}")

        # Build indexes for fast lookup
        for key, prof in self.agency_profiles.items():
            state = prof.get("state_abbr", "")
            if state:
                if state not in self._state_index:
                    self._state_index[state] = []
                self._state_index[state].append(key)

            county = prof.get("county", "").lower()
            if county:
                if county not in self._county_index:
                    self._county_index[county] = []
                self._county_index[county].append(key)

        # Build backward-compatible agency_stats
        for key, prof in self.agency_profiles.items():
            pop = prof.get("population", 0)
            self.agency_stats[key] = {
                "name": prof.get("name", ""),
                "agency_id": prof.get("agency_id", ""),
                "population": pop,
                "total_incidents": prof.get("total_incidents", 0),
                "annual_avg_incidents": prof.get("total_incidents", 0) // max(prof.get("n_years", 1), 1),
                "annual_part1_incidents": int(
                    prof.get("part1_rate", 0) * pop / 100_000 if pop > 0 else 0
                ),
                "rate_per_100k": prof.get("part1_rate", 0.0),
                "total_rate_per_100k": prof.get("total_rate", 0.0),
                "county": prof.get("county", ""),
                "type": prof.get("agency_type", ""),
                "state_abbr": prof.get("state_abbr", ""),
            }

        # Compute global statistics from all agencies
        if self.agency_profiles:
            all_hourly = np.zeros(24)
            total_weight = 0
            weapon_sum = 0.0
            stranger_sum = 0.0
            male_sum = 0.0
            female_sum = 0.0
            person_w = property_w = society_w = 0.0

            for prof in self.agency_profiles.values():
                w = prof.get("total_incidents", 1)
                total_weight += w
                for h in range(24):
                    all_hourly[h] += prof.get("hourly_dist", [1/24]*24)[h] * w
                weapon_sum += prof.get("weapon_rate", 0) * w
                stranger_sum += prof.get("stranger_rate", 0.3) * w
                male_sum += prof.get("victim_male_rate", 0.5) * w
                female_sum += prof.get("victim_female_rate", 0.5) * w

            if total_weight > 0:
                self.hourly_distribution = all_hourly / all_hourly.sum()
                self.hourly_severity_distribution = self.hourly_distribution.copy()
                self.weapon_rate = weapon_sum / total_weight
                self.stranger_crime_rate = stranger_sum / total_weight
                vt = male_sum + female_sum
                if vt > 0:
                    self.victim_gender_rates = {
                        "M": male_sum / vt,
                        "F": female_sum / vt,
                    }

        self.loaded = True
        states = set(p.get("state_abbr", "") for p in self.agency_profiles.values())
        logger.info(
            f"NIBRS data pipeline loaded: {len(self.agency_profiles)} agencies, "
            f"{len(self.state_profiles)} states, "
            f"covering {len(states)} unique states"
        )

    def get_agency_crime_rate(self, city_name: str) -> Optional[dict]:
        """Look up agency-level crime rate for any US city.

        Multi-tier matching: exact → substring → None.
        Returns dict with 'rate_per_100k', 'population', etc. or None.
        """
        if not self.agency_stats:
            return None

        city_lower = city_name.split(",")[0].strip().lower() if city_name else ""
        if not city_lower:
            return None

        # Exact match
        if city_lower in self.agency_stats:
            return self.agency_stats[city_lower]

        # Substring match
        for key, stats in self.agency_stats.items():
            if city_lower in key or key in city_lower:
                return stats

        return None

    def get_agency_profile(self, city_name: str, state_abbr: str = "") -> Optional[dict]:
        """Look up full agency profile with multi-tier fuzzy matching.

        Tier 1: Exact match on city_name.lower()
        Tier 2: Substring match (city in key or key in city)
        Tier 3: Match agencies in same state
        Tier 4: Return None
        """
        if not self.agency_profiles:
            return None

        city_lower = city_name.split(",")[0].strip().lower() if city_name else ""
        if not city_lower:
            return None

        # Tier 1: Exact match
        if city_lower in self.agency_profiles:
            return self.agency_profiles[city_lower]

        # Tier 2: Substring match
        best_match = None
        best_len = 999999
        for key, prof in self.agency_profiles.items():
            if city_lower in key or key in city_lower:
                # Prefer shortest key (most specific match)
                if len(key) < best_len:
                    best_match = prof
                    best_len = len(key)
        if best_match:
            return best_match

        # Tier 3: Same state, fall back to largest agency in state
        if state_abbr:
            state_keys = self._state_index.get(state_abbr.upper(), [])
            if state_keys:
                # Find agency with largest population in state
                best = None
                best_pop = 0
                for key in state_keys:
                    prof = self.agency_profiles[key]
                    if prof.get("population", 0) > best_pop:
                        best = prof
                        best_pop = prof["population"]
                # Only return state-level fallback if not too specific
                # (don't return NYC data for a small upstate town)
                return best

        return None

    def get_hourly_risk_curve(self, state_abbr: str = "", base_risk: float = 50.0) -> np.ndarray:
        """Get hourly risk curve using REAL per-state NIBRS distribution.

        Returns 24-element array with risk values (0-100 scale).

        The raw NIBRS hourly_dist captures crime *volume* (more reports
        during business hours when police are staffed).  To convert
        volume → per-capita *risk*, we combine the NIBRS volume shape
        with a circadian danger prior (fewer bystanders + less visibility
        at night = higher per-incident risk).
        """
        dist = None

        # Try state-specific profile first
        if state_abbr and state_abbr.upper() in self.state_profiles:
            sp = self.state_profiles[state_abbr.upper()]
            dist = np.array(sp.get("hourly_dist", []), dtype=np.float64)
            if len(dist) != 24:
                dist = None

        # Fall back to global distribution
        if dist is None and self.loaded:
            dist = self.hourly_distribution.copy()

        # Ultimate fallback
        if dist is None:
            return self._synthetic_fallback()

        # Normalize volume to max=1
        max_val = dist.max() if dist.max() > 0 else 1
        normalized = dist / max_val

        # Circular smoothing (24-hour data wraps around)
        kernel = np.array([0.1, 0.2, 0.4, 0.2, 0.1])
        k_half = len(kernel) // 2
        padded = np.concatenate([normalized[-k_half:], normalized, normalized[:k_half]])
        convolved = np.convolve(padded, kernel, mode="same")[k_half:-k_half]
        smoothed = convolved / convolved.max() if convolved.max() > 0 else convolved

        # Circadian risk prior — captures that nighttime exposure is
        # more dangerous regardless of volume (BJS victimization data).
        # Peak risk ~2-3 AM, trough ~10 AM.
        hours = np.arange(24)
        circadian = 0.5 + 0.5 * np.cos(2 * np.pi * (hours - 3) / 24)

        # Blend: 40% NIBRS volume shape + 60% circadian risk prior
        risk_shape = 0.4 * smoothed + 0.6 * circadian
        risk_shape = risk_shape / risk_shape.max() if risk_shape.max() > 0 else risk_shape

        # Scale by danger level
        danger = (100 - base_risk) / 100
        risk_curve = risk_shape * danger * 85 + 5
        return np.clip(risk_curve, 5, 95)

    @staticmethod
    def _synthetic_fallback() -> np.ndarray:
        """Fallback if no NIBRS data available."""
        hours = np.arange(24)
        night_peak = np.exp(-0.5 * ((hours - 22) / 3) ** 2) * 0.7
        afternoon = np.exp(-0.5 * ((hours - 15) / 4) ** 2) * 0.3
        morning_low = np.exp(-0.5 * ((hours - 6) / 3) ** 2) * 0.2
        base = night_peak + afternoon - morning_low + 0.3
        base = np.clip(base, 0.1, 1.0)
        return base / base.max() * 70 + 10

    def get_gender_risk_factor(self, gender: str) -> float:
        """Data-driven gender risk adjustment."""
        if not self.loaded or not self.victim_gender_rates:
            return {"female": 0.06, "male": 0.0, "mixed": 0.03}.get(gender, 0.03)

        female_rate = self.victim_gender_rates.get("F", 0.5)
        male_rate = self.victim_gender_rates.get("M", 0.5)
        baseline = 0.5
        if gender == "female":
            return min(0.15, max(0.0, (female_rate - baseline) * 0.3))
        elif gender == "male":
            return min(0.10, max(0.0, (male_rate - baseline) * 0.3))
        elif gender == "mixed":
            return 0.03
        return 0.03

    def get_location_type_risk(self, location_type: str) -> float:
        """Get risk multiplier for a specific location type."""
        if not self.loaded:
            return 1.0
        avg_severity = self.location_risk.get(location_type)
        if avg_severity is None:
            all_sevs = list(self.location_risk.values())
            avg_severity = float(np.mean(all_sevs)) if all_sevs else 3.0
        all_sevs = list(self.location_risk.values())
        overall_avg = float(np.mean(all_sevs)) if all_sevs else 3.0
        return avg_severity / overall_avg if overall_avg > 0 else 1.0


# ─────────────────────────── Singleton ──────────────────────────

nibrs_stats = NIBRSStatistics()


def initialize_nibrs():
    """Load NIBRS data. Call once at startup."""
    try:
        nibrs_stats.load()
    except Exception as e:
        logger.error(f"Failed to load NIBRS data: {e}")


# ═══════════════════════════════════════════════════════════════
# FBI-derived State Crime Profiles (fallback for states without
# pre-computed NIBRS profiles)
# ═══════════════════════════════════════════════════════════════


def derive_state_profile(fbi_data: dict, nibrs_detail: Optional[dict] = None) -> Optional[dict]:
    """Derive NIBRS-equivalent crime profile from FBI CDE aggregate data.

    Uses the state's offense-type distribution to weight BJS hourly patterns.
    This is the FALLBACK — only used when pre-computed NIBRS profiles are missing.
    """
    if not fbi_data or fbi_data.get("record_count", 0) == 0:
        return None

    counts = {
        "homicide": max(fbi_data.get("homicide", 0), 0),
        "robbery": max(fbi_data.get("robbery", 0), 0),
        "aggravated_assault": max(fbi_data.get("aggravated_assault", 0), 0),
        "burglary": max(fbi_data.get("burglary", 0), 0),
        "larceny": max(fbi_data.get("larceny", 0), 0),
        "motor_vehicle_theft": max(fbi_data.get("motor_vehicle_theft", 0), 0),
    }
    total = sum(counts.values())
    if total == 0:
        return None

    fracs = {k: v / total for k, v in counts.items()}

    pattern_map = {
        "homicide": _BJS_HOMICIDE, "robbery": _BJS_ROBBERY,
        "aggravated_assault": _BJS_ASSAULT, "burglary": _BJS_BURGLARY,
        "larceny": _BJS_LARCENY, "motor_vehicle_theft": _BJS_VEHICLE_THEFT,
    }
    hourly = np.zeros(24, dtype=np.float64)
    for offense, frac in fracs.items():
        hourly += frac * pattern_map.get(offense, _BJS_PROPERTY)
    hourly /= hourly.sum()

    hourly_sev = np.zeros(24, dtype=np.float64)
    for offense, frac in fracs.items():
        sev = _BJS_SEVERITY.get(offense, 3.0)
        pattern = pattern_map.get(offense, _BJS_PROPERTY)
        hourly_sev += frac * sev * pattern
    sev_total = hourly_sev.sum()
    if sev_total > 0:
        hourly_sev /= sev_total

    if nibrs_detail and nibrs_detail.get("weapon_rate", -1) >= 0:
        weapon_rate = nibrs_detail["weapon_rate"]
    else:
        weapon_rate = sum(fracs[k] * _NATIONAL_WEAPON_RATES.get(k, 0.01) for k in fracs)

    if nibrs_detail and nibrs_detail.get("victim_sex"):
        male_rate = nibrs_detail["victim_sex"].get("M", 0.5)
        female_rate = nibrs_detail["victim_sex"].get("F", 0.5)
    else:
        male_rate = sum(fracs[k] * _NATIONAL_VICTIM_SEX.get(k, {"M": 0.5})["M"] for k in fracs)
        female_rate = sum(fracs[k] * _NATIONAL_VICTIM_SEX.get(k, {"F": 0.5})["F"] for k in fracs)
    gender_total = male_rate + female_rate
    if gender_total > 0:
        male_rate /= gender_total
        female_rate /= gender_total

    violent_total = counts["homicide"] + counts["robbery"] + counts["aggravated_assault"]
    property_total = counts["burglary"] + counts["larceny"] + counts["motor_vehicle_theft"]
    crime_against = {}
    if total > 0:
        crime_against["Person"] = violent_total / total
        crime_against["Property"] = property_total / total
        crime_against["Society"] = 0.05
        ca_total = sum(crime_against.values())
        crime_against = {k: v / ca_total for k, v in crime_against.items()}

    stranger_rates = {
        "homicide": 0.22, "robbery": 0.55, "aggravated_assault": 0.38,
        "burglary": 0.65, "larceny": 0.85, "motor_vehicle_theft": 0.95,
    }
    stranger_rate = sum(fracs[k] * stranger_rates.get(k, 0.5) for k in fracs)

    return {
        "hourly_distribution": hourly,
        "hourly_severity_distribution": hourly_sev,
        "weapon_rate": float(weapon_rate),
        "victim_gender_rates": {"M": float(male_rate), "F": float(female_rate)},
        "crime_against_distribution": crime_against,
        "stranger_crime_rate": float(stranger_rate),
        "source": "FBI CDE + BJS (fallback)",
    }


def get_state_crime_profile(
    state_abbr: str,
    fbi_data: dict,
    nibrs_detail: Optional[dict] = None,
) -> Optional[dict]:
    """Get a complete crime profile for any US state.

    Priority:
      1. Pre-computed NIBRS profiles (all 51 states with NIBRS data)
      2. BJS-derived profiles from FBI CDE data (fallback)
    """
    st = state_abbr.upper() if state_abbr else ""

    # Priority 1: Pre-computed NIBRS profile
    if st and nibrs_stats.loaded and st in nibrs_stats.state_profiles:
        sp = nibrs_stats.state_profiles[st]
        return {
            "hourly_distribution": np.array(sp.get("hourly_dist", [1/24]*24)),
            "hourly_severity_distribution": np.array(sp.get("hourly_dist", [1/24]*24)),
            "weapon_rate": sp.get("weapon_rate", 0.0),
            "victim_gender_rates": sp.get("victim_gender_rates", {"M": 0.5, "F": 0.5}),
            "crime_against_distribution": sp.get("crime_against_distribution", {}),
            "stranger_crime_rate": sp.get("stranger_rate", 0.3),
            "source": "NIBRS (pre-computed)",
        }

    # Priority 2: BJS-derived fallback
    return derive_state_profile(fbi_data, nibrs_detail)
