"""Discover and bulk-download GPS-level crime incident data from Socrata open data portals.

Uses the Socrata Discovery API to find public-safety datasets across US cities,
then downloads incident records with lat/lng coordinates and normalizes them
into the format expected by the Lumos backend.

Output:
  - datasets/cities/{city_name}.json  — backend-compatible incident files
  - datasets/incidents.db             — SQLite database for geospatial queries

Prerequisites:
  pip install httpx python-dotenv tqdm

Usage:
  python scripts/collect_socrata_incidents.py discover                     # Discovery only
  python scripts/collect_socrata_incidents.py discover --state Georgia     # Discovery for a state
  python scripts/collect_socrata_incidents.py download                     # Download all discovered
  python scripts/collect_socrata_incidents.py download --state Georgia     # Download Georgia only
  python scripts/collect_socrata_incidents.py download --city Atlanta      # Download Atlanta only
  python scripts/collect_socrata_incidents.py download --max-records 50000 # Cap per dataset
  python scripts/collect_socrata_incidents.py status                       # Show collection stats
  python scripts/collect_socrata_incidents.py export                       # Re-export city JSONs
"""

import argparse
import json
import logging
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("socrata_collector")

ROOT_DIR = Path(__file__).resolve().parent.parent
CITIES_DIR = ROOT_DIR / "datasets" / "cities"
DB_PATH = ROOT_DIR / "datasets" / "incidents.db"
CATALOG_PATH = ROOT_DIR / "datasets" / "socrata_catalog.json"

SOCRATA_APP_TOKEN = os.getenv("SOCRATA_APP_TOKEN", "")

DISCOVERY_API = "https://api.us.socrata.com/api/catalog/v1"
DOWNLOAD_PAGE_SIZE = 50000
REQUEST_DELAY = 0.35

# ────────────── Column Detection Patterns ──────────────
# Exact-match only to avoid false positives like "violations" matching "lat"
LAT_PATTERNS = re.compile(
    r'^(lat|latitude|y_coord|y_coordinate|geocoded_latitude|point_y|ycoord|y|the_geom_latitude)$', re.I)
LNG_PATTERNS = re.compile(
    r'^(lng|lon|long|longitude|x_coord|x_coordinate|geocoded_longitude|point_x|xcoord|x|the_geom_longitude)$', re.I)
DATE_PATTERNS = re.compile(
    r'(^date$|datetime|occurred|reported|created_date|dispatch|call_date|incident_date|'
    r'report_date|arrest_date|event_date|from_date|start_date|cmplnt_fr_dt|date_occ|'
    r'offense_date|crime_date|date_reported|date_of_occurrence|occur_date)', re.I)
TYPE_PATTERNS = re.compile(
    r'(^type$|primary_type|desc|description|category|offense|offence|crime_type|'
    r'ucr|classification|charge|incident_type|ofns_desc|crm_cd_desc|nibrs|nature|'
    r'call_type|crime_category|offense_type|offense_desc|statute_desc)', re.I)

EXCLUDED_KEYWORDS = {
    "fire", "ems", "permit", "license", "inspection", "311",
    "parking", "zoning", "food", "restaurant", "animal",
    "pothole", "water", "sewer", "noise", "building",
    "census", "election", "voter", "budget", "salary",
    "construction", "demolition", "traffic collision", "traffic crash",
    "calls for service",
}

CRIME_KEYWORDS = {
    "crime", "incident", "offense", "arrest", "police",
    "criminal", "ucr", "nibrs", "violent", "property crime",
    "theft", "assault", "robbery", "burglary", "homicide",
    "larceny", "shooting", "stabbing", "battery",
}

# Search terms for Discovery API — empirically tested for best GPS-data yield
SEARCH_TERMS = [
    "crime latitude longitude",
    "crime incidents",
    "police crime reports",
    "criminal offenses",
    "police incidents",
    "crime data",
]

# Known Socrata domains with crime data — ensures coverage even if Discovery API misses them
CURATED_DOMAINS = {
    # Georgia
    "sharefulton.fultoncountyga.gov": {"state": "GA", "city": "Atlanta"},
    "performance.fultoncountyga.gov": {"state": "GA", "city": "Atlanta"},
    # Major cities already in the backend
    "data.cityofchicago.org": {"state": "IL", "city": "Chicago"},
    "data.cityofnewyork.us": {"state": "NY", "city": "New York"},
    "data.lacity.org": {"state": "CA", "city": "Los Angeles"},
    "data.sfgov.org": {"state": "CA", "city": "San Francisco"},
    "data.seattle.gov": {"state": "WA", "city": "Seattle"},
    "data.austintexas.gov": {"state": "TX", "city": "Austin"},
    "data.denvergov.org": {"state": "CO", "city": "Denver"},
    "data.nashville.gov": {"state": "TN", "city": "Nashville"},
    "www.dallasopendata.com": {"state": "TX", "city": "Dallas"},
    "data.houstontx.gov": {"state": "TX", "city": "Houston"},
    "data.baltimorecity.gov": {"state": "MD", "city": "Baltimore"},
    "data.detroitmi.gov": {"state": "MI", "city": "Detroit"},
    "opendata.minneapolismn.gov": {"state": "MN", "city": "Minneapolis"},
    "data.cityofsacramento.org": {"state": "CA", "city": "Sacramento"},
    "data.kcmo.org": {"state": "MO", "city": "Kansas City"},
    "data.sanantonio.gov": {"state": "TX", "city": "San Antonio"},
    "data.columbus.gov": {"state": "OH", "city": "Columbus"},
    "data.tucsonaz.gov": {"state": "AZ", "city": "Tucson"},
    "data.louisvilleky.gov": {"state": "KY", "city": "Louisville"},
    "data.stlouis-mo.gov": {"state": "MO", "city": "St. Louis"},
    "data.cincinnati-oh.gov": {"state": "OH", "city": "Cincinnati"},
    "data.charlottenc.gov": {"state": "NC", "city": "Charlotte"},
    "data.wprdc.org": {"state": "PA", "city": "Pittsburgh"},
    "data.mesaaz.gov": {"state": "AZ", "city": "Mesa"},
    "data.raleighnc.gov": {"state": "NC", "city": "Raleigh"},
    "data.oaklandca.gov": {"state": "CA", "city": "Oakland"},
    # Additional coverage
    "data.brla.gov": {"state": "LA", "city": "Baton Rouge"},
    "data.honolulu.gov": {"state": "HI", "city": "Honolulu"},
    "data.cityofgainesville.org": {"state": "FL", "city": "Gainesville"},
    "data.somervillema.gov": {"state": "MA", "city": "Somerville"},
    "data.cityofboise.org": {"state": "ID", "city": "Boise"},
    "data.providenceri.gov": {"state": "RI", "city": "Providence"},
    "data.nola.gov": {"state": "LA", "city": "New Orleans"},
    "data.buffalony.gov": {"state": "NY", "city": "Buffalo"},
    "data.cambridgema.gov": {"state": "MA", "city": "Cambridge"},
    "data.milwaukee.gov": {"state": "WI", "city": "Milwaukee"},
    "data.cityoftacoma.org": {"state": "WA", "city": "Tacoma"},
    "data.tempe.gov": {"state": "AZ", "city": "Tempe"},
    "data.hartford.gov": {"state": "CT", "city": "Hartford"},
    "data.kcpd.org": {"state": "MO", "city": "Kansas City"},
    "data.virginia-beach.va.us": {"state": "VA", "city": "Virginia Beach"},
    "data.norfolk.gov": {"state": "VA", "city": "Norfolk"},
    "data.burlingtonvt.gov": {"state": "VT", "city": "Burlington"},
    "data.montgomerycountymd.gov": {"state": "MD", "city": "Montgomery County"},
    "data.jacksonms.gov": {"state": "MS", "city": "Jackson"},
    "www.transparentrichmond.org": {"state": "VA", "city": "Richmond"},
    "data.cityofmadison.com": {"state": "WI", "city": "Madison"},
    "data.chattanooga.gov": {"state": "TN", "city": "Chattanooga"},
    "data.lexingtonky.gov": {"state": "KY", "city": "Lexington"},
    "data.memphis.gov": {"state": "TN", "city": "Memphis"},
    "data.fortworthtexas.gov": {"state": "TX", "city": "Fort Worth"},
    "data.townofcary.org": {"state": "NC", "city": "Cary"},
}

US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine",
    "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska",
    "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island",
    "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
    "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}
STATE_ABBR_TO_NAME = US_STATES
STATE_NAME_TO_ABBR = {v.lower(): k for k, v in US_STATES.items()}


# ──────────────────────── Database Setup ─────────────────────────

def init_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS datasets (
            dataset_id  TEXT PRIMARY KEY,
            domain      TEXT NOT NULL,
            name        TEXT NOT NULL,
            description TEXT,
            city        TEXT,
            state       TEXT,
            lat_field   TEXT,
            lng_field   TEXT,
            date_field  TEXT,
            type_field  TEXT,
            point_field TEXT,
            row_count   INTEGER DEFAULT 0,
            downloaded  INTEGER DEFAULT 0,
            last_fetched TEXT,
            is_valid    INTEGER DEFAULT 1,
            metadata    TEXT
        );

        CREATE TABLE IF NOT EXISTS incidents (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            dataset_id  TEXT NOT NULL,
            lat         REAL NOT NULL,
            lng         REAL NOT NULL,
            crime_type  TEXT,
            incident_date TEXT,
            raw_json    TEXT,
            FOREIGN KEY (dataset_id) REFERENCES datasets(dataset_id)
        );

        CREATE INDEX IF NOT EXISTS idx_incidents_geo
            ON incidents(lat, lng);
        CREATE INDEX IF NOT EXISTS idx_incidents_dataset
            ON incidents(dataset_id);
        CREATE INDEX IF NOT EXISTS idx_incidents_date
            ON incidents(incident_date);
        CREATE INDEX IF NOT EXISTS idx_datasets_city
            ON datasets(city);
        CREATE INDEX IF NOT EXISTS idx_datasets_state
            ON datasets(state);
    """)
    return conn


# ──────────────────────── Column Detection ───────────────────────

def _detect_columns(columns: list[dict]) -> dict:
    """Auto-detect lat, lng, date, type, and point columns from metadata."""
    fields = {}
    field_names = [c.get("fieldName", "") for c in columns]
    field_types = [c.get("dataTypeName", "") for c in columns]

    for name, dtype in zip(field_names, field_types):
        if LAT_PATTERNS.match(name) and "lat_field" not in fields:
            fields["lat_field"] = name
        elif LNG_PATTERNS.match(name) and "lng_field" not in fields:
            fields["lng_field"] = name
        elif dtype.lower() == "point" and "point_field" not in fields:
            fields["point_field"] = name

    for name in field_names:
        if DATE_PATTERNS.search(name) and "date_field" not in fields:
            fields["date_field"] = name

    for name in field_names:
        if TYPE_PATTERNS.search(name) and "type_field" not in fields:
            fields["type_field"] = name

    has_geo = ("lat_field" in fields and "lng_field" in fields) or "point_field" in fields
    return fields if has_geo else {}


def _score_dataset(name: str, description: str) -> float:
    """Score relevance: higher = more likely to be useful crime incident data."""
    text = f"{name} {description}".lower()
    score = 0.0
    for kw in CRIME_KEYWORDS:
        if kw in text:
            score += 2.0
    for kw in EXCLUDED_KEYWORDS:
        if kw in text:
            score -= 3.0
    return score


def _extract_city_state(entry: dict, domain: str) -> tuple[str, str]:
    """Extract city and state from a Discovery API entry, using domain hints."""
    city, state = "", ""

    # Check curated domains first
    if domain in CURATED_DOMAINS:
        info = CURATED_DOMAINS[domain]
        return info.get("city", ""), info.get("state", "")

    # Check classification metadata
    classification = entry.get("classification", {})
    for meta in classification.get("domain_metadata", []):
        key = (meta.get("key", "") or "").lower()
        val = meta.get("value", "") or ""
        if not val:
            continue
        if "city" in key or "jurisdiction" in key:
            city = val
        elif "state" in key:
            state = val

    # Infer city from domain name
    if not city:
        m = re.match(r'(?:data|opendata|open)\.(?:city\s*of\s*)?(\w+)', domain, re.I)
        if m:
            raw = m.group(1)
            if len(raw) > 2 and raw.lower() not in ("gov", "org", "com", "us"):
                city = raw.title()

    # State from domain_tags
    if not state:
        for tag in classification.get("domain_tags", []):
            if tag.lower() in STATE_NAME_TO_ABBR:
                state = STATE_NAME_TO_ABBR[tag.lower()]
                break

    return city, state


# ──────────────────────── Discovery Phase ────────────────────────

def discover_via_search(client: httpx.Client, state_filter: str = "",
                        city_filter: str = "") -> dict[str, dict]:
    """Global discovery via Socrata Discovery API search."""
    datasets = {}

    for term in SEARCH_TERMS:
        offset = 0
        while True:
            params = {
                "q": term,
                "only": "datasets",
                "limit": 100,
                "offset": offset,
            }
            headers = {"X-App-Token": SOCRATA_APP_TOKEN} if SOCRATA_APP_TOKEN else {}

            try:
                r = client.get(DISCOVERY_API, params=params, headers=headers, timeout=30)
                if r.status_code != 200:
                    break

                data = r.json()
                results = data.get("results", [])
                if not results:
                    break

                for entry in results:
                    resource = entry.get("resource", {})
                    dataset_id = resource.get("id", "")
                    if not dataset_id or dataset_id in datasets:
                        continue

                    name = resource.get("name", "")
                    description = resource.get("description", "")
                    score = _score_dataset(name, description)
                    if score <= 0:
                        continue

                    cols = resource.get("columns_field_name", [])
                    types = resource.get("columns_datatype", [])
                    col_dicts = [{"fieldName": n, "dataTypeName": t} for n, t in zip(cols, types)]
                    detected = _detect_columns(col_dicts)
                    if not detected:
                        continue

                    domain = entry.get("metadata", {}).get("domain", "")
                    city, state = _extract_city_state(entry, domain)

                    if state_filter:
                        if state.lower() != state_filter.lower() and \
                           STATE_ABBR_TO_NAME.get(state.upper(), "").lower() != state_filter.lower():
                            continue
                    if city_filter and city_filter.lower() not in city.lower():
                        continue

                    datasets[dataset_id] = {
                        "dataset_id": dataset_id,
                        "domain": domain,
                        "name": name,
                        "description": description[:500],
                        "city": city,
                        "state": state,
                        "score": score,
                        **detected,
                    }

                total_available = data.get("resultSetSize", 0)
                offset += 100
                if offset >= total_available:
                    break
                time.sleep(REQUEST_DELAY)

            except Exception as e:
                logger.error(f"Discovery error for '{term}' offset={offset}: {e}")
                break

        logger.info(f"  Search '{term}': {len(datasets)} total qualifying datasets")

    return datasets


def discover_via_domains(client: httpx.Client, state_filter: str = "",
                         city_filter: str = "") -> dict[str, dict]:
    """Search within curated Socrata domains for crime datasets."""
    datasets = {}

    domains_to_check = CURATED_DOMAINS
    if state_filter:
        sf = state_filter.upper() if len(state_filter) == 2 else \
             STATE_NAME_TO_ABBR.get(state_filter.lower(), state_filter.upper())
        domains_to_check = {d: info for d, info in CURATED_DOMAINS.items()
                            if info.get("state", "").upper() == sf}
    if city_filter:
        domains_to_check = {d: info for d, info in domains_to_check.items()
                            if city_filter.lower() in info.get("city", "").lower()}

    for domain, info in domains_to_check.items():
        for term in ["crime", "police incidents", "offenses"]:
            params = {
                "domains": domain,
                "q": term,
                "only": "datasets",
                "limit": 50,
            }
            headers = {"X-App-Token": SOCRATA_APP_TOKEN} if SOCRATA_APP_TOKEN else {}

            try:
                r = client.get(DISCOVERY_API, params=params, headers=headers, timeout=20)
                if r.status_code != 200:
                    continue

                data = r.json()
                for entry in data.get("results", []):
                    resource = entry.get("resource", {})
                    dataset_id = resource.get("id", "")
                    if not dataset_id or dataset_id in datasets:
                        continue

                    name = resource.get("name", "")
                    description = resource.get("description", "")

                    cols = resource.get("columns_field_name", [])
                    types = resource.get("columns_datatype", [])
                    col_dicts = [{"fieldName": n, "dataTypeName": t} for n, t in zip(cols, types)]
                    detected = _detect_columns(col_dicts)
                    if not detected:
                        continue

                    datasets[dataset_id] = {
                        "dataset_id": dataset_id,
                        "domain": domain,
                        "name": name,
                        "description": description[:500],
                        "city": info.get("city", ""),
                        "state": info.get("state", ""),
                        "score": _score_dataset(name, description),
                        **detected,
                    }

                time.sleep(REQUEST_DELAY)

            except Exception as e:
                logger.debug(f"Domain search error for {domain}/{term}: {e}")

        if any(d["domain"] == domain for d in datasets.values()):
            matching = sum(1 for d in datasets.values() if d["domain"] == domain)
            logger.info(f"  {domain}: {matching} datasets found")

    return datasets


def enrich_dataset_metadata(client: httpx.Client, ds: dict) -> dict:
    """Fetch full column metadata to refine field detection and get row count."""
    url = f"https://{ds['domain']}/api/views/{ds['dataset_id']}.json"
    headers = {"X-App-Token": SOCRATA_APP_TOKEN} if SOCRATA_APP_TOKEN else {}

    try:
        r = client.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            return ds

        meta = r.json()
        columns = meta.get("columns", [])
        detected = _detect_columns(columns)
        if detected:
            ds.update(detected)

        row_count = meta.get("rowCount") or 0
        ds["row_count"] = int(row_count)

        if not ds.get("city"):
            custom = meta.get("metadata", {}).get("custom_fields", {})
            for section in custom.values():
                if isinstance(section, dict):
                    for k, v in section.items():
                        if "city" in k.lower() or "jurisdiction" in k.lower():
                            ds["city"] = str(v)
                            break

    except Exception as e:
        logger.debug(f"Metadata enrichment failed for {ds['dataset_id']}: {e}")

    return ds


def save_catalog(datasets: list[dict]):
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CATALOG_PATH, "w") as f:
        json.dump({"updated": datetime.utcnow().isoformat(), "datasets": datasets}, f, indent=2)
    logger.info(f"Catalog saved: {CATALOG_PATH} ({len(datasets)} datasets)")


def load_catalog() -> list[dict]:
    if CATALOG_PATH.exists():
        with open(CATALOG_PATH) as f:
            return json.load(f).get("datasets", [])
    return []


def persist_catalog_to_db(conn: sqlite3.Connection, datasets: list[dict]):
    for ds in datasets:
        conn.execute("""
            INSERT OR REPLACE INTO datasets
                (dataset_id, domain, name, description, city, state,
                 lat_field, lng_field, date_field, type_field, point_field,
                 row_count, is_valid, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        """, (
            ds["dataset_id"], ds["domain"], ds["name"], ds.get("description", ""),
            ds.get("city", ""), ds.get("state", ""),
            ds.get("lat_field"), ds.get("lng_field"), ds.get("date_field"),
            ds.get("type_field"), ds.get("point_field"),
            ds.get("row_count", 0),
            json.dumps({"score": ds.get("score", 0)}),
        ))
    conn.commit()


# ──────────────────────── Download Phase ─────────────────────────

def _extract_lat_lng(record: dict, ds: dict) -> tuple[float | None, float | None]:
    lat_field = ds.get("lat_field")
    lng_field = ds.get("lng_field")
    point_field = ds.get("point_field")

    lat, lng = None, None

    if lat_field and lng_field:
        try:
            lat = float(record.get(lat_field, 0))
            lng = float(record.get(lng_field, 0))
        except (ValueError, TypeError):
            lat, lng = None, None

    if (lat is None or lng is None or lat == 0 or lng == 0) and point_field:
        point = record.get(point_field)
        if isinstance(point, dict):
            try:
                lat = float(point.get("latitude", 0))
                lng = float(point.get("longitude", 0))
            except (ValueError, TypeError):
                lat, lng = None, None
        elif isinstance(point, str):
            m = re.match(r'POINT\s*\(\s*([-\d.]+)\s+([-\d.]+)\s*\)', point, re.I)
            if m:
                lng, lat = float(m.group(1)), float(m.group(2))

    if lat and lng and -90 <= lat <= 90 and -180 <= lng <= 180:
        if 24 <= lat <= 50 and -130 <= lng <= -60:
            return round(lat, 6), round(lng, 6)
    return None, None


def _extract_date(record: dict, ds: dict) -> str | None:
    date_field = ds.get("date_field")
    if not date_field:
        return None
    raw = record.get(date_field)
    if not raw:
        return None
    return str(raw).strip()[:19]


def _extract_type(record: dict, ds: dict) -> str:
    type_field = ds.get("type_field")
    if not type_field:
        return "Unknown"
    raw = record.get(type_field, "Unknown")
    if raw is None:
        return "Unknown"
    return str(raw).strip().title()[:100]


def download_dataset(client: httpx.Client, conn: sqlite3.Connection, ds: dict,
                     max_records: int = 500_000) -> int:
    """Download all records from a single Socrata dataset with pagination."""
    dataset_id = ds["dataset_id"]
    domain = ds["domain"]
    base_url = f"https://{domain}/resource/{dataset_id}.json"

    existing = conn.execute(
        "SELECT downloaded FROM datasets WHERE dataset_id = ?", (dataset_id,)
    ).fetchone()
    if existing and existing[0] and existing[0] > 0:
        logger.info(f"  Skip {dataset_id} ({ds['name'][:40]}): {existing[0]} records already downloaded")
        return existing[0]

    headers = {"X-App-Token": SOCRATA_APP_TOKEN} if SOCRATA_APP_TOKEN else {}

    select_fields = []
    for f in [ds.get("type_field"), ds.get("date_field"),
              ds.get("lat_field"), ds.get("lng_field"), ds.get("point_field")]:
        if f and f not in select_fields:
            select_fields.append(f)

    one_year_ago = (datetime.utcnow() - timedelta(days=365)).strftime('%Y-%m-%dT00:00:00')
    date_field = ds.get("date_field")

    total_inserted = 0
    offset = 0
    consecutive_empties = 0
    retry_without_filter = False

    while offset < max_records:
        params = {
            "$limit": min(DOWNLOAD_PAGE_SIZE, max_records - offset),
            "$offset": offset,
            "$order": ":id",
        }
        if select_fields:
            params["$select"] = ",".join(select_fields)
        if date_field and not retry_without_filter:
            params["$where"] = f"{date_field} > '{one_year_ago}'"

        try:
            r = client.get(base_url, params=params, headers=headers, timeout=90)

            if r.status_code == 400 and not retry_without_filter:
                retry_without_filter = True
                params.pop("$where", None)
                r = client.get(base_url, params=params, headers=headers, timeout=90)

            if r.status_code != 200:
                logger.warning(f"  HTTP {r.status_code} for {domain}/{dataset_id} at offset {offset}")
                if r.status_code == 429:
                    time.sleep(5)
                    continue
                break

            records = r.json()
            if not isinstance(records, list) or len(records) == 0:
                consecutive_empties += 1
                if consecutive_empties >= 2:
                    break
                offset += DOWNLOAD_PAGE_SIZE
                continue

            consecutive_empties = 0
            batch = []
            for rec in records:
                lat, lng = _extract_lat_lng(rec, ds)
                if lat is None or lng is None:
                    continue
                crime_type = _extract_type(rec, ds)
                incident_date = _extract_date(rec, ds)
                batch.append((dataset_id, lat, lng, crime_type, incident_date, None))

            if batch:
                conn.executemany("""
                    INSERT INTO incidents (dataset_id, lat, lng, crime_type, incident_date, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, batch)
                conn.commit()
                total_inserted += len(batch)

            if len(records) < DOWNLOAD_PAGE_SIZE:
                break

            offset += len(records)
            time.sleep(REQUEST_DELAY)

        except httpx.TimeoutException:
            logger.warning(f"  Timeout at offset {offset} for {dataset_id}")
            break
        except Exception as e:
            logger.error(f"  Error at offset {offset} for {dataset_id}: {e}")
            break

    conn.execute("""
        UPDATE datasets SET downloaded = ?, last_fetched = ? WHERE dataset_id = ?
    """, (total_inserted, datetime.utcnow().isoformat(), dataset_id))
    conn.commit()

    return total_inserted


# ─────────────────── Export to City JSON Files ───────────────────

def export_city_json(conn: sqlite3.Connection, max_per_city: int = 10_000):
    """Export recent incidents grouped by city to compact JSON files for the backend.

    The SQLite DB is the primary query path (via _query_local_incidents_db in
    data_fetchers.py). These JSON files serve as a lightweight fallback.
    """
    CITIES_DIR.mkdir(parents=True, exist_ok=True)

    cities = conn.execute("""
        SELECT DISTINCT d.city, d.state
        FROM datasets d
        JOIN incidents i ON d.dataset_id = i.dataset_id
        WHERE d.city != '' AND d.city IS NOT NULL
    """).fetchall()

    exported = 0
    for city, state in cities:
        city_key = re.sub(r'[^\w]', '_', city.lower().replace(" ", "_")).strip("_")
        if not city_key:
            continue

        total = conn.execute("""
            SELECT COUNT(*) FROM incidents i
            JOIN datasets d ON i.dataset_id = d.dataset_id
            WHERE LOWER(d.city) = LOWER(?)
        """, (city,)).fetchone()[0]

        rows = conn.execute("""
            SELECT i.lat, i.lng, i.crime_type, i.incident_date
            FROM incidents i
            JOIN datasets d ON i.dataset_id = d.dataset_id
            WHERE LOWER(d.city) = LOWER(?)
            ORDER BY i.incident_date DESC
            LIMIT ?
        """, (city, max_per_city)).fetchall()

        if not rows:
            continue

        incidents = []
        for lat, lng, crime_type, incident_date in rows:
            inc = {"lat": lat, "lng": lng, "type": crime_type or "Unknown"}
            if incident_date:
                inc["date"] = incident_date
            incidents.append(inc)

        from datetime import timezone
        out = {
            "city": city,
            "state": state or "",
            "updated": datetime.now(timezone.utc).isoformat(),
            "total_count": total,
            "exported_count": len(incidents),
            "incidents": incidents,
        }

        out_path = CITIES_DIR / f"{city_key}.json"
        with open(out_path, "w") as f:
            json.dump(out, f)

        exported += 1
        logger.info(f"  Exported {city}, {state}: {len(incidents):,}/{total:,} incidents -> {out_path.name}")

    logger.info(f"Exported {exported} city files to {CITIES_DIR}")


# ──────────────────────── Status Report ──────────────────────────

def print_status(conn: sqlite3.Connection):
    total_ds = conn.execute("SELECT COUNT(*) FROM datasets").fetchone()[0]
    fetched_ds = conn.execute("SELECT COUNT(*) FROM datasets WHERE downloaded > 0").fetchone()[0]
    total_inc = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]

    print(f"\n{'='*65}")
    print(f"  Socrata GPS-Level Incident Collection Status")
    print(f"{'='*65}")
    print(f"  Cataloged datasets:   {total_ds}")
    print(f"  Downloaded datasets:  {fetched_ds}")
    print(f"  Total GPS incidents:  {total_inc:,}")
    if DB_PATH.exists():
        print(f"  Database size:        {DB_PATH.stat().st_size / (1024*1024):.1f} MB")

    print(f"\n  Top cities by incident count:")
    top = conn.execute("""
        SELECT d.city, d.state, COUNT(*) as cnt
        FROM incidents i JOIN datasets d ON i.dataset_id = d.dataset_id
        WHERE d.city != ''
        GROUP BY LOWER(d.city), d.state
        ORDER BY cnt DESC LIMIT 20
    """).fetchall()
    for city, state, count in top:
        print(f"    {city}, {state}: {count:,}")

    print(f"\n  States covered:")
    states = conn.execute("""
        SELECT d.state, COUNT(DISTINCT d.dataset_id) as ds, COUNT(i.id) as inc
        FROM datasets d LEFT JOIN incidents i ON d.dataset_id = i.dataset_id
        WHERE d.state != ''
        GROUP BY d.state ORDER BY inc DESC
    """).fetchall()
    for state, ds_count, inc_count in states:
        print(f"    {state}: {ds_count} datasets, {inc_count:,} incidents")

    exported = list(CITIES_DIR.glob("*.json")) if CITIES_DIR.exists() else []
    print(f"\n  Exported city JSON files: {len(exported)}")
    print(f"{'='*65}\n")


# ──────────────────────── CLI Commands ───────────────────────────

def cmd_discover(args):
    logger.info("Starting Socrata dataset discovery (global search + curated domains)...")
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        logger.info("Phase 1: Global Discovery API search...")
        search_datasets = discover_via_search(
            client, state_filter=args.state or "", city_filter=args.city or "")

        logger.info("Phase 2: Curated domain-specific search...")
        domain_datasets = discover_via_domains(
            client, state_filter=args.state or "", city_filter=args.city or "")

        all_datasets = {**search_datasets, **domain_datasets}
        logger.info(f"Combined: {len(all_datasets)} unique datasets")

        if not all_datasets:
            logger.warning("No datasets found.")
            return

        logger.info(f"Phase 3: Enriching metadata for {len(all_datasets)} datasets...")
        enriched = []
        ds_list = list(all_datasets.values())
        iterator = tqdm(ds_list, desc="Enriching metadata") if tqdm else ds_list
        for ds in iterator:
            ds = enrich_dataset_metadata(client, ds)
            if ds.get("lat_field") or ds.get("lng_field") or ds.get("point_field"):
                enriched.append(ds)
            time.sleep(REQUEST_DELAY)

        enriched.sort(key=lambda d: d.get("row_count", 0), reverse=True)
        save_catalog(enriched)

        conn = init_db()
        persist_catalog_to_db(conn, enriched)
        conn.close()

        logger.info(f"\nDiscovery complete: {len(enriched)} datasets with GPS columns")
        logger.info("Top datasets by row count:")
        for ds in enriched[:15]:
            logger.info(f"  [{ds['dataset_id']}] {ds.get('city','?'):15s} {ds.get('state','?'):5s} "
                        f"rows={ds.get('row_count',0):>10,}  {ds['name'][:50]}")


def cmd_download(args):
    conn = init_db()

    catalog = load_catalog()
    if not catalog:
        logger.info("No catalog found — running discovery first...")
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            search_ds = discover_via_search(client, args.state or "", args.city or "")
            domain_ds = discover_via_domains(client, args.state or "", args.city or "")
            all_ds = {**search_ds, **domain_ds}
            catalog = []
            for ds in all_ds.values():
                ds = enrich_dataset_metadata(client, ds)
                if ds.get("lat_field") or ds.get("lng_field") or ds.get("point_field"):
                    catalog.append(ds)
                time.sleep(REQUEST_DELAY)
            save_catalog(catalog)
            persist_catalog_to_db(conn, catalog)

    if args.state:
        sf = args.state.upper() if len(args.state) == 2 else \
             STATE_NAME_TO_ABBR.get(args.state.lower(), args.state.upper())
        catalog = [d for d in catalog if d.get("state", "").upper() == sf or
                   STATE_ABBR_TO_NAME.get(d.get("state", "").upper(), "").lower() == args.state.lower()]
        logger.info(f"Filtered to {len(catalog)} datasets for state: {args.state}")
    if args.city:
        catalog = [d for d in catalog if args.city.lower() in d.get("city", "").lower()]
        logger.info(f"Filtered to {len(catalog)} datasets for city: {args.city}")

    if not catalog:
        logger.warning("No datasets to download.")
        conn.close()
        return

    catalog.sort(key=lambda d: d.get("row_count", 0), reverse=True)
    max_records = args.max_records or 500_000
    total_downloaded = 0
    successful = 0

    logger.info(f"Downloading from {len(catalog)} datasets (max {max_records:,} per dataset)...")

    with httpx.Client(timeout=90, follow_redirects=True) as client:
        for i, ds in enumerate(catalog, 1):
            label = f"[{i}/{len(catalog)}] {ds.get('city', '?')}/{ds['dataset_id']}"
            try:
                count = download_dataset(client, conn, ds, max_records=max_records)
                if count > 0:
                    successful += 1
                    total_downloaded += count
                    logger.info(f"  {label}: {count:,} GPS incidents")
                else:
                    logger.info(f"  {label}: 0 GPS incidents (skipped or empty)")
            except Exception as e:
                logger.error(f"  {label}: FAILED — {e}")

    logger.info(f"\nDownload complete: {total_downloaded:,} incidents from {successful} datasets")

    logger.info("Exporting city JSON files for backend...")
    export_city_json(conn)
    print_status(conn)
    conn.close()


def cmd_status(args):
    if not DB_PATH.exists():
        print("No database found. Run 'discover' first.")
        return
    conn = init_db()
    print_status(conn)
    conn.close()


def cmd_export(args):
    if not DB_PATH.exists():
        print("No database found. Run 'download' first.")
        return
    conn = init_db()
    export_city_json(conn)
    conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Collect GPS-level crime incidents from Socrata open data portals",
    )
    sub = parser.add_subparsers(dest="command")

    p_disc = sub.add_parser("discover", help="Find crime datasets with GPS coordinates")
    p_disc.add_argument("--state", help="Filter by state (name or abbreviation)")
    p_disc.add_argument("--city", help="Filter by city name")
    p_disc.set_defaults(func=cmd_discover)

    p_dl = sub.add_parser("download", help="Download incidents from discovered datasets")
    p_dl.add_argument("--state", help="Filter by state")
    p_dl.add_argument("--city", help="Filter by city")
    p_dl.add_argument("--max-records", type=int, default=500_000,
                      help="Max records per dataset (default: 500k)")
    p_dl.set_defaults(func=cmd_download)

    p_st = sub.add_parser("status", help="Show collection statistics")
    p_st.set_defaults(func=cmd_status)

    p_ex = sub.add_parser("export", help="Re-export city JSON files from DB")
    p_ex.set_defaults(func=cmd_export)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
