"""Lumos Backend — Configuration & Constants"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (one level up from backend/)
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)

# ── API Keys ──
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")
DATA_GOV_API_KEY = os.environ.get("DATA_GOV_API_KEY", "DEMO_KEY")
GEMINI_API_KEY = os.environ.get("VITE_GEMINI_API_KEY", "")

# ── Socrata Open Data Network Keys ──
SOCRATA_APP_TOKEN = os.environ.get("SOCRATA_APP_TOKEN", "")
SOCRATA_SECRET_TOKEN = os.environ.get("SOCRATA_SECRET_TOKEN", "")
SOCRATA_KEY_ID = os.environ.get("SOCRATA_KEY_ID", "")
SOCRATA_KEY_SECRET = os.environ.get("SOCRATA_KEY_SECRET", "")
FBI_CDE_BASE = "https://api.usa.gov/crime/fbi/cde"

# ── Dynamic APIs ──
TICKETMASTER_API_KEY = os.environ.get("TICKETMASTER_API_KEY", "")
CRIMEOMETER_API_KEY = os.environ.get("CRIMEOMETER_API_KEY", "")
ASTRONOMY_APP_ID = os.environ.get("ASTRONOMY_APP_ID", "")
ASTRONOMY_APP_SECRET = os.environ.get("ASTRONOMY_APP_SECRET", "")
OPENWEATHERMAP_API_KEY = os.environ.get("OPENWEATHERMAP_API_KEY", "")

# ML feature names (XGBoost v2) — order MUST match train_safety_model.py
FEATURE_NAMES = [
    "agency_part1_rate",
    "agency_violent_rate",
    "agency_property_rate",
    "agency_weapon_rate",
    "agency_stranger_rate",
    "agency_severity_score",
    "state_crime_rate_norm",
    "population_group",
    "hourly_risk_ratio",
    "dow_risk_ratio",
    "monthly_risk_ratio",
    "time_sin",
    "time_cos",
    "is_weekend",
    "people_count_norm",
    "gender_factor",
    "weather_severity",
    "officer_density",
    "is_college",
    "is_urban",
    "poi_density",
    "live_events_norm",
    "live_incidents_norm",
    "moon_illumination",
    "spatial_density_score",
]

# Crime type → icon mapping
ICON_MAP = {
    "theft": "🔓", "larceny": "🔓", "grand larceny": "🔓", "petit larceny": "🔓",
    "shoplifting": "🔓", "pickpocket": "🔓", "property": "🔓",
    "burglary": "🏠", "breaking": "🏠", "trespass": "🏠",
    "robbery": "💰", "armed robbery": "💰",
    "assault": "⚠️", "battery": "⚠️", "aggravated assault": "⚠️",
    "vehicle": "🚗", "motor vehicle theft": "🚗", "auto theft": "🚗",
    "car": "🚗", "vehicle break-in": "🚗",
    "vandalism": "🏚️", "criminal damage": "🏚️", "mischief": "🏚️",
    "arson": "🔥", "fire": "🔥",
    "homicide": "☠️", "murder": "☠️",
    "drugs": "💊", "narcotic": "💊",
    "sexual": "🚨", "sex offense": "🚨", "rape": "🚨",
    "fraud": "📋", "forgery": "📋", "identity theft": "📋",
    "weapon": "🔫", "weapons": "🔫", "gun": "🔫",
    "dui": "🍺", "dwi": "🍺", "alcohol": "🍺",
}

# City-specific non-emergency phone numbers
CITY_NON_EMERGENCY = {
    "new york": "311",
    "chicago": "311",
    "los angeles": "877-275-5273",
    "san francisco": "415-553-0123",
    "seattle": "206-625-5011",
    "atlanta": "404-546-4235",
    "boston": "617-343-4911",
    "denver": "720-913-2000",
    "austin": "311",
    "philadelphia": "311",
    "houston": "713-884-3131",
    "phoenix": "602-262-6151",
    "dallas": "311",
}

# International emergency numbers by country code
INTERNATIONAL_EMERGENCY = {
    "US": {"emergency": "911", "label": "Emergency (US)"},
    "GB": {"emergency": "999", "label": "Emergency (UK)"},
    "EU": {"emergency": "112", "label": "Emergency (EU)"},
    "AU": {"emergency": "000", "label": "Emergency (AU)"},
    "JP": {"emergency": "110", "label": "Police (JP)"},
    "IN": {"emergency": "112", "label": "Emergency (IN)"},
    "CA": {"emergency": "911", "label": "Emergency (CA)"},
    "MX": {"emergency": "911", "label": "Emergency (MX)"},
    "BR": {"emergency": "190", "label": "Police (BR)"},
    "DEFAULT": {"emergency": "112", "label": "Emergency"},
}
