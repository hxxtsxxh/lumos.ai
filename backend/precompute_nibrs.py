"""Lumos Backend — NIBRS Pre-computation Pipeline

Streams ALL 51 states' NIBRS CSV data and produces two JSON artifacts:
  1. datasets/agency_profiles.json   — per-agency crime statistics
  2. datasets/state_temporal_profiles.json — per-state temporal distributions

Run from project root:
    python backend/precompute_nibrs.py
"""

import csv
import json
import logging
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
logger = logging.getLogger("precompute")

# ── Paths ──────────────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
_DATASETS_DIR = _PROJECT_ROOT / "datasets"

# FBI UCR Part I Index Crimes (NIBRS offense codes)
_PART_I_OFFENSE_CODES = {
    "09A", "09B", "11A", "11B", "11C", "11D", "120", "13A",
    "200", "220", "23A", "23B", "23C", "23D", "23E", "23F", "23G", "23H", "240",
}

# Violent Part I subset
_VIOLENT_CODES = {"09A", "09B", "11A", "11B", "11C", "11D", "120", "13A"}

# Property Part I subset
_PROPERTY_CODES = {"200", "220", "23A", "23B", "23C", "23D", "23E", "23F", "23G", "23H", "240"}

# Offense severity overrides (same as nibrs_data.py)
_CRIME_AGAINST_WEIGHT = {"Person": 8.0, "Property": 3.0, "Society": 2.0, "Not a Crime": 0.5}
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

# ── Helpers ────────────────────────────────────────────────────

def _safe_int(val, default=0):
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _safe_float(val, default=0.0):
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _find_csv(directory: Path, name: str) -> Path | None:
    """Case-insensitive file search in a directory."""
    name_lower = name.lower()
    for f in directory.iterdir():
        if f.name.lower() == name_lower:
            return f
    return None


def _stream_csv(filepath: Path):
    """Stream CSV rows with UPPERCASE-normalised column names."""
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield {k.upper(): v for k, v in row.items()}


def _parse_incident_date(raw: str):
    """Parse incident date into a datetime object.

    Handles:
      - 2024-01-01            (ISO)
      - 2010-01-25 00:00:00   (ISO with time)
      - 09-DEC-18             (DD-Mon-YY)
      - 15-JAN-18 12:00:00    (DD-Mon-YY HH:MI:SS)
      - 01/15/2024            (MM/DD/YYYY)
    """
    if not raw or not raw.strip():
        return None
    raw = raw.strip().strip('"')
    for fmt in (
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%d-%b-%y",
        "%d-%b-%y %H:%M:%S",
        "%d-%b-%Y",
        "%d-%b-%Y %H:%M:%S",
        "%m/%d/%Y",
    ):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _discover_directories() -> list[tuple[str, int, Path]]:
    """Find all [A-Z]{2}-\\d{4} directories under datasets/."""
    pattern = re.compile(r"^([A-Z]{2})-(\d{4})$")
    dirs = []
    for d in sorted(_DATASETS_DIR.iterdir()):
        if d.is_dir():
            m = pattern.match(d.name)
            if m:
                dirs.append((m.group(1), int(m.group(2)), d))
    return dirs


# ── Per-agency accumulator ─────────────────────────────────────

class AgencyAccumulator:
    """Accumulates statistics per agency across multiple state-year dirs."""

    def __init__(self):
        # agency_id -> accumulated stats
        self.hourly = defaultdict(lambda: [0] * 24)
        self.dow = defaultdict(lambda: [0] * 7)
        self.monthly = defaultdict(lambda: [0] * 12)
        self.total_incidents = defaultdict(int)
        self.years_seen = defaultdict(set)       # agency_id -> set of years
        self.offense_counts = defaultdict(lambda: defaultdict(int))  # agency -> code -> count
        self.part1_counts = defaultdict(int)
        self.violent_counts = defaultdict(int)
        self.property_counts = defaultdict(int)
        self.severity_weighted = defaultdict(float)
        self.total_offenses = defaultdict(int)
        self.weapon_offense_count = defaultdict(int)  # agency -> count of offenses w/ weapon
        self.victim_male = defaultdict(int)
        self.victim_female = defaultdict(int)
        self.victim_age_sum = defaultdict(float)
        self.victim_age_count = defaultdict(int)
        self.stranger_count = defaultdict(int)
        self.total_rels = defaultdict(int)

        # agency_id -> info dict (kept most recent / highest pop)
        self.agency_info: dict[str, dict] = {}

        # incident_id -> agency_id mapping (per directory processing)
        # These are reset per directory to save memory
        self._incident_agency: dict[str, str] = {}
        self._offense_incident: dict[str, str] = {}  # offense_id -> incident_id


def _load_offense_type_lookup(directory: Path) -> tuple[dict, dict]:
    """Load NIBRS_OFFENSE_TYPE.csv from a directory.

    Returns (by_id, by_code) lookups.
    """
    fp = _find_csv(directory, "NIBRS_OFFENSE_TYPE.csv")
    if not fp:
        return {}, {}

    by_id, by_code = {}, {}
    for row in _stream_csv(fp):
        name = row.get("OFFENSE_NAME", "Unknown").strip()
        crime_against = row.get("CRIME_AGAINST", "").strip()
        severity = _OFFENSE_SEVERITY_OVERRIDES.get(
            name, _CRIME_AGAINST_WEIGHT.get(crime_against, 2.0)
        )
        info = {
            "name": name,
            "crime_against": crime_against,
            "severity": severity,
            "offense_code": row.get("OFFENSE_CODE", "").strip(),
        }
        ot_id = row.get("OFFENSE_TYPE_ID", "")
        if ot_id:
            by_id[_safe_int(ot_id)] = info
        ot_code = row.get("OFFENSE_CODE", "").strip()
        if ot_code:
            by_code[ot_code] = info
    return by_id, by_code


def _process_directory(state: str, year: int, directory: Path, acc: AgencyAccumulator):
    """Process a single state-year directory, accumulating into acc."""

    # ── 1. Agencies ──
    agencies_file = _find_csv(directory, "agencies.csv")
    if not agencies_file:
        agencies_file = _find_csv(directory, "cde_agencies.csv")
    if agencies_file:
        for row in _stream_csv(agencies_file):
            aid = row.get("AGENCY_ID", "")
            if not aid:
                continue
            pop = _safe_int(row.get("POPULATION", 0))
            name = row.get("PUB_AGENCY_NAME", "").strip()
            if not name:
                name = row.get("UCR_AGENCY_NAME", "").strip()
            prev = acc.agency_info.get(aid)
            if not prev or pop > prev.get("population", 0):
                pop_group_raw = row.get("POPULATION_GROUP_CODE", "0")
                # Extract numeric portion from codes like "6", "1E", "8D"
                pg_num = _safe_int(re.sub(r"[^0-9]", "", str(pop_group_raw)), 0)
                acc.agency_info[aid] = {
                    "name": name,
                    "population": pop,
                    "county": row.get("COUNTY_NAME", "").strip(),
                    "state_abbr": row.get("STATE_ABBR", state).strip() or state,
                    "agency_type": row.get("AGENCY_TYPE_NAME", "").strip(),
                    "population_group": pg_num,
                    "male_officer": _safe_int(row.get("MALE_OFFICER", 0)),
                    "female_officer": _safe_int(row.get("FEMALE_OFFICER", 0)),
                }

    # ── 2. Incidents ──
    incident_file = _find_csv(directory, "NIBRS_incident.csv")
    if not incident_file:
        return  # No incident data — skip this directory

    # Clear per-directory caches
    acc._incident_agency.clear()
    acc._offense_incident.clear()

    for row in _stream_csv(incident_file):
        inc_id = row.get("INCIDENT_ID", "")
        aid = row.get("AGENCY_ID", "")
        if not inc_id or not aid:
            continue

        key = f"{year}:{inc_id}"
        acc._incident_agency[inc_id] = aid
        acc.total_incidents[aid] += 1
        acc.years_seen[aid].add(year)

        # Hour
        hour = _safe_int(row.get("INCIDENT_HOUR", ""), -1)
        if 0 <= hour <= 23:
            acc.hourly[aid][hour] += 1

        # Date parsing for DOW and month
        date_raw = row.get("INCIDENT_DATE", "")
        dt = _parse_incident_date(date_raw)
        if dt:
            acc.dow[aid][dt.weekday()] += 1
            acc.monthly[aid][dt.month - 1] += 1

    # ── 3. Offense type lookup ──
    ot_by_id, ot_by_code = _load_offense_type_lookup(directory)

    # ── 4. Offenses ──
    offense_file = _find_csv(directory, "NIBRS_OFFENSE.csv")
    if offense_file:
        for row in _stream_csv(offense_file):
            off_id = row.get("OFFENSE_ID", "")
            inc_id = row.get("INCIDENT_ID", "")
            aid = acc._incident_agency.get(inc_id, "")
            if not aid:
                continue

            if off_id:
                acc._offense_incident[off_id] = inc_id

            # Resolve offense code
            ot_code = row.get("OFFENSE_CODE", "").strip()
            ot_id_val = row.get("OFFENSE_TYPE_ID", "")
            ot_info = {}
            if ot_id_val:
                ot_info = ot_by_id.get(_safe_int(ot_id_val), {})
            if not ot_code and ot_info:
                ot_code = ot_info.get("offense_code", "")
            if not ot_info and ot_code:
                ot_info = ot_by_code.get(ot_code, {})

            resolved_code = ot_code.upper() if ot_code else ""

            acc.total_offenses[aid] += 1
            if resolved_code:
                acc.offense_counts[aid][resolved_code] += 1

            severity = ot_info.get("severity", 2.0) if ot_info else 2.0
            acc.severity_weighted[aid] += severity

            if resolved_code in _PART_I_OFFENSE_CODES:
                acc.part1_counts[aid] += 1
            if resolved_code in _VIOLENT_CODES:
                acc.violent_counts[aid] += 1
            if resolved_code in _PROPERTY_CODES:
                acc.property_counts[aid] += 1

    # ── 5. Weapons ──
    weapon_file = _find_csv(directory, "NIBRS_WEAPON.csv")
    if weapon_file:
        for row in _stream_csv(weapon_file):
            off_id = row.get("OFFENSE_ID", "")
            inc_id = acc._offense_incident.get(off_id, "")
            if not inc_id:
                # Try using INCIDENT_ID directly if available
                inc_id = row.get("INCIDENT_ID", "")
            aid = acc._incident_agency.get(inc_id, "")
            if aid:
                acc.weapon_offense_count[aid] += 1

    # ── 6. Victims ──
    victim_file = _find_csv(directory, "NIBRS_VICTIM.csv")
    if victim_file:
        for row in _stream_csv(victim_file):
            inc_id = row.get("INCIDENT_ID", "")
            aid = acc._incident_agency.get(inc_id, "")
            if not aid:
                continue
            sex = row.get("SEX_CODE", "").strip()
            if sex == "M":
                acc.victim_male[aid] += 1
            elif sex == "F":
                acc.victim_female[aid] += 1
            age_num = _safe_int(row.get("AGE_NUM", ""), -1)
            if 0 < age_num < 120:
                acc.victim_age_sum[aid] += age_num
                acc.victim_age_count[aid] += 1

    # ── 7. Victim-Offender Relationships ──
    rel_file = _find_csv(directory, "NIBRS_VICTIM_OFFENDER_REL.csv")
    if rel_file:
        # Load relationship lookup
        rel_lookup_file = _find_csv(directory, "NIBRS_RELATIONSHIP.csv")
        rel_names = {}
        if rel_lookup_file:
            for row in _stream_csv(rel_lookup_file):
                rel_id = _safe_int(row.get("RELATIONSHIP_ID", ""))
                rel_names[rel_id] = row.get("RELATIONSHIP_NAME", "").strip()

        for row in _stream_csv(rel_file):
            # Try to find the agency from victim -> incident
            victim_id = row.get("VICTIM_ID", "")
            inc_id = row.get("INCIDENT_ID", "")
            # Some formats don't have INCIDENT_ID in rel file,
            # so we try the victim_id approach via incident_agency
            aid = acc._incident_agency.get(inc_id, "") if inc_id else ""
            if not aid:
                # Can't determine agency, skip
                continue

            acc.total_rels[aid] += 1
            rel_id = _safe_int(row.get("RELATIONSHIP_ID", ""))
            rel_name = rel_names.get(rel_id, "").lower()
            if "stranger" in rel_name or "unknown" in rel_name:
                acc.stranger_count[aid] += 1


def _build_agency_profiles(acc: AgencyAccumulator) -> dict:
    """Convert accumulators into the final agency profiles dict."""
    profiles = {}
    for aid, info in acc.agency_info.items():
        total_inc = acc.total_incidents.get(aid, 0)
        if total_inc < 50:
            continue  # Skip low-data agencies

        pop = info.get("population", 0)
        n_years = max(len(acc.years_seen.get(aid, set())), 1)
        latest_year = max(acc.years_seen.get(aid, {0}))

        # Annual rates per 100K
        if pop > 0:
            part1_rate = (acc.part1_counts.get(aid, 0) / n_years) / pop * 100_000
            violent_rate = (acc.violent_counts.get(aid, 0) / n_years) / pop * 100_000
            property_rate = (acc.property_counts.get(aid, 0) / n_years) / pop * 100_000
            total_rate = (total_inc / n_years) / pop * 100_000
        else:
            part1_rate = violent_rate = property_rate = total_rate = 0.0

        total_off = max(acc.total_offenses.get(aid, 0), 1)
        weapon_rate = acc.weapon_offense_count.get(aid, 0) / total_off

        total_rels_count = max(acc.total_rels.get(aid, 0), 1)
        stranger_rate = acc.stranger_count.get(aid, 0) / total_rels_count

        total_victims = acc.victim_male.get(aid, 0) + acc.victim_female.get(aid, 0)
        if total_victims > 0:
            victim_female_rate = acc.victim_female.get(aid, 0) / total_victims
            victim_male_rate = acc.victim_male.get(aid, 0) / total_victims
        else:
            victim_female_rate = victim_male_rate = 0.5

        mean_victim_age = 0.0
        if acc.victim_age_count.get(aid, 0) > 0:
            mean_victim_age = acc.victim_age_sum[aid] / acc.victim_age_count[aid]

        officers = info.get("male_officer", 0) + info.get("female_officer", 0)
        officers_per_1000 = (officers / pop * 1000) if pop > 0 else 0.0

        severity_score = acc.severity_weighted.get(aid, 0) / total_off

        # Offense mix (top 20 codes)
        off_counts = acc.offense_counts.get(aid, {})
        if off_counts:
            sorted_codes = sorted(off_counts.items(), key=lambda x: -x[1])[:20]
            total_coded = sum(c for _, c in sorted_codes) or 1
            offense_mix = {code: round(cnt / total_coded, 4) for code, cnt in sorted_codes}
        else:
            offense_mix = {}

        # Hourly distribution (normalized)
        hourly_raw = acc.hourly.get(aid, [0] * 24)
        h_total = sum(hourly_raw) or 1
        hourly_dist = [round(h / h_total, 6) for h in hourly_raw]

        # DOW distribution
        dow_raw = acc.dow.get(aid, [0] * 7)
        d_total = sum(dow_raw) or 1
        dow_dist = [round(d / d_total, 6) for d in dow_raw]

        # Monthly distribution
        monthly_raw = acc.monthly.get(aid, [0] * 12)
        m_total = sum(monthly_raw) or 1
        monthly_dist = [round(m / m_total, 6) for m in monthly_raw]

        name = info.get("name", "")
        key = name.lower().strip()
        if not key:
            continue

        # If duplicate name, append state
        if key in profiles:
            state = info.get("state_abbr", "")
            key = f"{key} ({state})"

        profiles[key] = {
            "agency_id": aid,
            "name": name,
            "state_abbr": info.get("state_abbr", ""),
            "county": info.get("county", ""),
            "population": pop,
            "population_group": info.get("population_group", 0),
            "agency_type": info.get("agency_type", ""),
            "n_years": n_years,
            "total_incidents": total_inc,
            "latest_year": latest_year,
            "part1_rate": round(part1_rate, 1),
            "violent_rate": round(violent_rate, 1),
            "property_rate": round(property_rate, 1),
            "total_rate": round(total_rate, 1),
            "weapon_rate": round(weapon_rate, 4),
            "stranger_rate": round(stranger_rate, 4),
            "victim_female_rate": round(victim_female_rate, 4),
            "victim_male_rate": round(victim_male_rate, 4),
            "mean_victim_age": round(mean_victim_age, 1),
            "officers_per_1000": round(officers_per_1000, 2),
            "severity_score": round(severity_score, 3),
            "offense_mix": offense_mix,
            "hourly_dist": hourly_dist,
            "dow_dist": dow_dist,
            "monthly_dist": monthly_dist,
        }

    return profiles


def _build_state_profiles(profiles: dict) -> dict:
    """Aggregate agency profiles into per-state profiles."""
    state_data = defaultdict(lambda: {
        "hourly": [0] * 24, "dow": [0] * 7, "monthly": [0] * 12,
        "total_incidents": 0, "n_agencies": 0,
        "weapon_weighted": 0.0, "total_offenses_for_weapon": 0,
        "stranger_weighted": 0.0, "total_rels_for_stranger": 0,
        "victim_m": 0, "victim_f": 0,
        "person_weighted": 0.0, "property_weighted": 0.0, "society_weighted": 0.0,
        "total_off_for_ca": 0,
    })

    for _key, prof in profiles.items():
        st = prof.get("state_abbr", "")
        if not st:
            continue
        sd = state_data[st]
        inc = prof["total_incidents"]
        sd["total_incidents"] += inc
        sd["n_agencies"] += 1

        for h in range(24):
            sd["hourly"][h] += prof["hourly_dist"][h] * inc
        for d in range(7):
            sd["dow"][d] += prof["dow_dist"][d] * inc
        for m in range(12):
            sd["monthly"][m] += prof["monthly_dist"][m] * inc

        sd["weapon_weighted"] += prof["weapon_rate"] * inc
        sd["total_offenses_for_weapon"] += inc
        sd["stranger_weighted"] += prof["stranger_rate"] * inc
        sd["total_rels_for_stranger"] += inc

        total_v = inc  # use incident count as weight
        sd["victim_m"] += prof["victim_male_rate"] * total_v
        sd["victim_f"] += prof["victim_female_rate"] * total_v

        # Crime-against from offense mix (approximate)
        for code, frac in prof.get("offense_mix", {}).items():
            weighted = frac * inc
            if code in _VIOLENT_CODES:
                sd["person_weighted"] += weighted
            elif code in _PROPERTY_CODES:
                sd["property_weighted"] += weighted
            else:
                sd["society_weighted"] += weighted
            sd["total_off_for_ca"] += weighted

    result = {}
    for st, sd in state_data.items():
        total = max(sd["total_incidents"], 1)

        h_total = sum(sd["hourly"]) or 1
        hourly_dist = [round(h / h_total, 6) for h in sd["hourly"]]

        d_total = sum(sd["dow"]) or 1
        dow_dist = [round(d / d_total, 6) for d in sd["dow"]]

        m_total = sum(sd["monthly"]) or 1
        monthly_dist = [round(m / m_total, 6) for m in sd["monthly"]]

        weapon_denom = max(sd["total_offenses_for_weapon"], 1)
        stranger_denom = max(sd["total_rels_for_stranger"], 1)
        victim_total = max(sd["victim_m"] + sd["victim_f"], 1)
        ca_total = max(sd["total_off_for_ca"], 1)

        result[st] = {
            "hourly_dist": hourly_dist,
            "dow_dist": dow_dist,
            "monthly_dist": monthly_dist,
            "total_incidents": sd["total_incidents"],
            "n_agencies": sd["n_agencies"],
            "weapon_rate": round(sd["weapon_weighted"] / weapon_denom, 4),
            "stranger_rate": round(sd["stranger_weighted"] / stranger_denom, 4),
            "victim_gender_rates": {
                "M": round(sd["victim_m"] / victim_total, 4),
                "F": round(sd["victim_f"] / victim_total, 4),
            },
            "crime_against_distribution": {
                "Person": round(sd["person_weighted"] / ca_total, 4),
                "Property": round(sd["property_weighted"] / ca_total, 4),
                "Society": round(sd["society_weighted"] / ca_total, 4),
            },
        }

    return result


def main():
    t0 = time.time()
    logger.info("Discovering NIBRS state-year directories...")
    dirs = _discover_directories()
    logger.info(f"Found {len(dirs)} state-year directories")

    if not dirs:
        logger.error(f"No state-year directories found under {_DATASETS_DIR}")
        sys.exit(1)

    acc = AgencyAccumulator()
    processed = 0
    skipped = 0

    for state, year, directory in dirs:
        incident_file = _find_csv(directory, "NIBRS_incident.csv")
        if not incident_file:
            skipped += 1
            continue

        try:
            _process_directory(state, year, directory, acc)
            processed += 1
        except Exception as e:
            logger.warning(f"Error processing {directory.name}: {e}")
            skipped += 1
            continue

        if processed % 10 == 0:
            elapsed = time.time() - t0
            logger.info(
                f"  Progress: {processed}/{len(dirs)} dirs processed "
                f"({skipped} skipped), {len(acc.agency_info)} agencies, "
                f"{elapsed:.0f}s elapsed"
            )

    logger.info(
        f"Processing complete: {processed} dirs processed, {skipped} skipped, "
        f"{len(acc.agency_info)} total agencies found"
    )

    # Build profiles
    logger.info("Building agency profiles...")
    agency_profiles = _build_agency_profiles(acc)
    logger.info(f"  {len(agency_profiles)} agency profiles (≥50 incidents)")

    logger.info("Building state temporal profiles...")
    state_profiles = _build_state_profiles(agency_profiles)
    logger.info(f"  {len(state_profiles)} state profiles")

    # Save artifacts
    out_agency = _DATASETS_DIR / "agency_profiles.json"
    out_state = _DATASETS_DIR / "state_temporal_profiles.json"

    logger.info(f"Writing {out_agency}...")
    with open(out_agency, "w") as f:
        json.dump(agency_profiles, f, indent=1)
    sz_agency = out_agency.stat().st_size / (1024 * 1024)
    logger.info(f"  agency_profiles.json: {sz_agency:.1f} MB")

    logger.info(f"Writing {out_state}...")
    with open(out_state, "w") as f:
        json.dump(state_profiles, f, indent=1)
    sz_state = out_state.stat().st_size / (1024 * 1024)
    logger.info(f"  state_temporal_profiles.json: {sz_state:.1f} MB")

    elapsed = time.time() - t0
    logger.info(f"Done in {elapsed:.0f}s ({elapsed / 60:.1f} min)")

    # Summary
    states_with_data = set()
    for _k, p in agency_profiles.items():
        states_with_data.add(p["state_abbr"])
    logger.info(f"States with agency data: {len(states_with_data)} — {sorted(states_with_data)}")


if __name__ == "__main__":
    main()
