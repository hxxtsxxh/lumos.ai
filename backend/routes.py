"""Lumos Backend — FastAPI Routes"""

import asyncio
import math
import logging
import time
import uuid
from datetime import datetime, timezone
import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import GOOGLE_MAPS_API_KEY, GEMINI_API_KEY
from models import (
    SafetyRequest, RouteRequest, UserReport,
    SafetyResponse, RouteResponse, HistoricalResponse,
    UserReportResponse, IncidentType, TimeAnalysis,
    DataSource, HeatmapPoint, HourlyRisk, NearbyPOI,
    RouteSegment, HistoricalDataPoint, AISafetyTipsRequest,
    WeatherInfo, LiveIncident, SafetyChatRequest,
)
from data_fetchers import (
    client, fetch_fbi_crime_data, fetch_fbi_historical,
    fetch_fbi_nibrs_detail,
    fetch_city_crime_data, fetch_nws_weather,
    fetch_census_population, fetch_state_from_coords,
    reverse_geocode_city, fetch_country_from_coords,
    fetch_nearby_pois, fetch_route_directions,
    fetch_local_events, fetch_moon_illumination, fetch_live_incidents,
    fetch_citizen_incidents,
)
from scoring import (
    compute_safety_score,
    compute_heatmap_from_incidents,
    get_emergency_numbers, build_incident_types,
    estimate_local_crime_rate,
    gemini_refine_score,
    gemini_enrich_heatmap,
    update_incident_crime_level,
    compute_live_incident_penalty,
    compute_citizen_adjustment,
)
from ml_model import safety_model
from nibrs_data import initialize_nibrs, get_state_crime_profile

logger = logging.getLogger("lumos")


async def _noop_dict() -> dict:
    """Async no-op returning empty dict, for use in asyncio.gather when a fetch should be skipped."""
    return {}


# ─────────────────────────── App Setup ──────────────────────────

app = FastAPI(title="Lumos Safety API", version="3.0.0")

_allowed_origins = [
    f"http://localhost:{p}" for p in range(3000, 3010)
] + [
    f"http://localhost:{p}" for p in range(5173, 5180)
] + [
    f"http://localhost:{p}" for p in range(8080, 8090)
] + [
    f"http://127.0.0.1:{p}" for p in range(3000, 3010)
] + [
    f"http://127.0.0.1:{p}" for p in range(5173, 5180)
] + [
    f"http://127.0.0.1:{p}" for p in range(8080, 8090)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────── Startup Event ──────────────────────

@app.on_event("startup")
async def startup_event():
    """Initialize NIBRS data pipeline on startup."""
    initialize_nibrs()
    logger.info("XGBoost model will lazy-load on first prediction")


# ─────────────────────────── Rate Limiting ──────────────────────

_rate_store: dict[str, list[float]] = {}
RATE_LIMIT = 30  # requests per minute per IP
RATE_WINDOW = 60  # seconds
_RATE_EVICT_INTERVAL = 300  # evict stale IPs every 5 minutes
_last_rate_evict = 0.0


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    from fastapi.responses import JSONResponse
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()

    # Periodically evict stale IPs to prevent memory leak
    global _last_rate_evict
    if now - _last_rate_evict > _RATE_EVICT_INTERVAL:
        stale_ips = [ip for ip, timestamps in _rate_store.items()
                     if not timestamps or now - timestamps[-1] > RATE_WINDOW * 2]
        for ip in stale_ips:
            del _rate_store[ip]
        _last_rate_evict = now

    # Clean old entries for this IP
    if client_ip in _rate_store:
        _rate_store[client_ip] = [t for t in _rate_store[client_ip] if now - t < RATE_WINDOW]
    else:
        _rate_store[client_ip] = []

    if len(_rate_store[client_ip]) >= RATE_LIMIT:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Try again in a minute."},
        )

    _rate_store[client_ip].append(now)
    return await call_next(request)


# ─────────────────────────── In-memory user reports ─────────────

user_reports: list[dict] = []


# ─────────────────────────── Main Safety Endpoint ───────────────

@app.post("/api/safety", response_model=SafetyResponse)
async def get_safety_data(req: SafetyRequest):
    city = req.locationName or ""
    if not city:
        city = await reverse_geocode_city(req.lat, req.lng)

    logger.info(f"Safety request: {city} ({req.lat:.4f}, {req.lng:.4f})")

    state_abbr = await fetch_state_from_coords(req.lat, req.lng)

    fbi_data, city_crime_result, weather, population, country_code, pois, nibrs_detail, live_events, live_incidents, moon_illumination, citizen_incidents = await asyncio.gather(
        fetch_fbi_crime_data(state_abbr),
        fetch_city_crime_data(req.lat, req.lng, city),
        fetch_nws_weather(req.lat, req.lng),
        fetch_census_population(req.lat, req.lng),
        fetch_country_from_coords(req.lat, req.lng),
        fetch_nearby_pois(req.lat, req.lng),
        fetch_fbi_nibrs_detail(state_abbr) if state_abbr else _noop_dict(),
        fetch_local_events(req.lat, req.lng),
        fetch_live_incidents(req.lat, req.lng),
        fetch_moon_illumination(req.lat, req.lng),
        fetch_citizen_incidents(req.lat, req.lng),
    )

    city_incidents = city_crime_result.get("incidents", [])
    total_annual_crime = city_crime_result.get("total_annual_count", len(city_incidents))

    # Build state-level crime profile FIRST (needed for data sources & scoring)
    crime_profile = get_state_crime_profile(state_abbr, fbi_data, nibrs_detail)

    # Data sources
    data_sources = []
    if fbi_data:
        data_sources.append(DataSource(
            name="FBI Crime Data Explorer (UCR)",
            lastUpdated=f"{fbi_data.get('year', 2023)}-12-31",
            recordCount=fbi_data.get("record_count", 0),
        ))
    if crime_profile:
        profile_src = crime_profile.get("source", "FBI CDE + BJS")
        data_sources.append(DataSource(
            name=f"Crime Profile ({profile_src})",
            lastUpdated=f"{fbi_data.get('year', 2023)}-12-31" if fbi_data else "2023-12-31",
            recordCount=fbi_data.get("record_count", 0) if fbi_data else 0,
        ))
    if city_incidents:
        city_name = city.split(",")[0].strip() if city else "City"
        data_sources.append(DataSource(
            name=f"{city_name} Open Data Portal",
            lastUpdated=datetime.utcnow().strftime("%Y-%m-%d"),
            recordCount=total_annual_crime,
        ))
    if weather.get("alert_count", 0) > 0:
        data_sources.append(DataSource(
            name="National Weather Service Alerts",
            lastUpdated=datetime.utcnow().strftime("%Y-%m-%d"),
            recordCount=weather["alert_count"],
        ))
    data_sources.append(DataSource(
        name="U.S. Census Bureau (Population)",
        lastUpdated="2020-04-01",
        recordCount=population,
    ))

    # Crime rate — estimate LOCAL rate rather than using raw state average
    crime_rate_per_100k = 0.0
    state_rate_per_100k = 0.0
    if fbi_data and fbi_data.get("population"):
        total_crime = fbi_data.get("violent_crime", 0) + fbi_data.get("property_crime", 0)
        state_rate_per_100k = (total_crime / fbi_data["population"]) * 100_000
        # Adjust for local area type (urban/suburban/rural)
        crime_rate_per_100k = estimate_local_crime_rate(
            state_rate_per_100k,
            population,
            city_name=city,
            city_incidents=city_incidents,
            total_annual_crime=total_annual_crime,
            state_abbr=state_abbr,
        )
    elif total_annual_crime > 0 and population > 0:
        crime_rate_per_100k = min((total_annual_crime / population) * 100_000, 8000)

    try:
        hour = int(req.timeOfTravel.split(":")[0])
        if not (0 <= hour <= 23):
            hour = 12
    except (ValueError, IndexError):
        hour = 12

    # Incident types — built AFTER crime rate so we can pass the crime level context
    incident_types = build_incident_types(
        city_incidents, fbi_data, crime_rate_per_100k,
        user_lat=req.lat, user_lng=req.lng,
        city_name=city, state_abbr=state_abbr,
        location=req.locationName or "",
        hour=hour,
    )

    # Extract dynamic location features
    city_lower = (city or "").lower()
    is_college = 1.0 if any(k in city_lower for k in ["university", "college", "institute", "tech"]) else 0.0
    if not is_college and pois:
        if any("university" in p.get("type", "").lower() or "college" in p.get("name", "").lower() for p in pois):
            is_college = 1.0
    is_urban = 1.0 if population > 250_000 else 0.0
    is_weekend = 1.0 if datetime.utcnow().weekday() >= 5 else 0.0
    poi_density = min(len(pois) / 50.0, 1.0) if pois else 0.0
    is_after_sunset = 1.0 if (hour >= 18 or hour < 6) else 0.0

    _total_live = len(live_incidents) + len(citizen_incidents)
    safety_index, _ = compute_safety_score(
        crime_rate_per_100k, hour, req.peopleCount, req.gender,
        weather.get("max_severity", 0.0), population,
        city_incidents, safety_model,
        duration_minutes=req.duration,
        state_abbr=state_abbr,
        crime_profile=crime_profile,
        is_college=is_college,
        is_urban=is_urban,
        is_weekend=is_weekend,
        poi_density=poi_density,
        lat=req.lat,
        lng=req.lng,
        live_events=live_events,
        live_incidents=_total_live,
        moon_illumination=moon_illumination,
        city_name=city,
    )

    risk_level = "safe" if safety_index >= 70 else "caution" if safety_index >= 40 else "danger"

    # ── Unified Live-Incident Penalty (Citizen + Socrata/NWS) ──
    # Normalise open-data incidents into the same dict shape the penalty expects.
    _unified_incidents: list[dict] = list(citizen_incidents)
    for inc in live_incidents:
        _sev = str(inc.get("severity", "")).lower()
        _level = 2 if _sev in ("extreme", "severe") else 1 if _sev == "moderate" else 0
        _ts = 0
        if inc.get("date"):
            try:
                _dt_obj = datetime.fromisoformat(str(inc["date"]).replace("Z", "+00:00"))
                _ts = int(_dt_obj.timestamp() * 1000)
            except (ValueError, TypeError):
                pass
        _unified_incidents.append({
            "lat": inc.get("lat"),
            "lng": inc.get("lng"),
            "ts": _ts,
            "level": _level,
            "severity": _sev or "moderate",
            "incidentScore": 0.5 if _level >= 1 else 0.1,
            "source": inc.get("source", "open_data"),
            "title": inc.get("type", ""),
            "closed": False,
            "confirmed": True,
            "isGoodNews": False,
        })

    live_penalty = compute_live_incident_penalty(
        target_lat=req.lat,
        target_lng=req.lng,
        all_incidents=_unified_incidents,
        current_hour=hour,
        target_hour=None,
    )
    if live_penalty > 0:
        safety_index = max(5, safety_index - int(round(live_penalty)))
        risk_level = "safe" if safety_index >= 70 else "caution" if safety_index >= 40 else "danger"
        logger.info(
            f"Live-incident penalty={live_penalty:.1f} "
            f"({len(citizen_incidents)} citizen + {len(live_incidents)} open-data), "
            f"adjusted safety_index={safety_index}"
        )

    # ── Build live incident summary for Gemini context (before refinement) ──
    _live_summary_parts = []
    for inc in live_incidents[:8]:
        parts = [inc.get("type", "Unknown")]
        if inc.get("distance_miles"):
            parts.append(f"{inc['distance_miles']:.1f}mi away")
        if inc.get("severity"):
            parts.append(str(inc["severity"]))
        _live_summary_parts.append(", ".join(parts))
    for inc in citizen_incidents[:8]:
        sev_map = {"red": "severe", "yellow": "moderate", "green": "minor", "grey": "minor"}
        parts = [inc.get("title", "Incident")]
        sev_label = sev_map.get(inc.get("severity", ""), "moderate")
        parts.append(sev_label)
        _live_summary_parts.append(", ".join(parts))
    live_incident_summary = "; ".join(_live_summary_parts[:12]) if _live_summary_parts else ""

    # ── Gemini refinement layer (now with live incident context) ──
    safety_index = await gemini_refine_score(
        safety_index,
        city_name=city,
        state_abbr=state_abbr,
        hour=hour,
        crime_rate=crime_rate_per_100k,
        weather_condition=weather.get("owm_condition", "Clear"),
        weather_severity=weather.get("max_severity", 0.0),
        people_count=req.peopleCount,
        gender=req.gender,
        incident_types=[it.type for it in incident_types[:5]],
        live_incident_summary=live_incident_summary,
        live_incident_count=len(_unified_incidents),
    )
    risk_level = "safe" if safety_index >= 70 else "caution" if safety_index >= 40 else "danger"

    # Update crime level tags to match the FINAL safety score (ML + Gemini)
    update_incident_crime_level(incident_types, safety_index)

    # Compute a true 24-hour trace utilizing the full dimension set (ML natively shifts peak)
    hourly_risk = []
    risk_values = []
    
    def format_hour(start_h):
        h = start_h % 24
        if h == 0: return "12a"
        elif h < 12: return f"{h}a"
        elif h == 12: return "12p"
        else: return f"{h-12}p"

    for h in range(24):
        h_is_after_sunset = 1.0 if (h >= 18 or h < 6) else 0.0
        s_idx, _ = compute_safety_score(
            crime_rate_per_100k, h, req.peopleCount, req.gender,
            weather.get("max_severity", 0.0), population, city_incidents, safety_model,
            duration_minutes=req.duration, state_abbr=state_abbr, crime_profile=crime_profile,
            is_college=is_college, is_urban=is_urban, is_weekend=is_weekend,
            poi_density=poi_density,
            lat=req.lat, lng=req.lng,
            live_events=live_events, live_incidents=_total_live,
            moon_illumination=moon_illumination,
            city_name=city,
        )
        h_penalty = compute_live_incident_penalty(
            target_lat=req.lat,
            target_lng=req.lng,
            all_incidents=_unified_incidents,
            current_hour=hour,
            target_hour=h,
        )
        s_idx = max(5, s_idx - int(round(h_penalty)))
        risk_val = 100 - s_idx
        risk_values.append(risk_val)

    # ── Amplify temporal contrast ──
    # The ML model produces modest hour-to-hour swings (typically 10-17 pts).
    # Amplify deviations from the 24-hour mean by ~2.5× so the chart clearly
    # shows the day/night swing while keeping the mean risk truthful.
    mean_risk = sum(risk_values) / 24
    TEMPORAL_AMP = 2.5
    amplified = [
        max(5, min(95, round(mean_risk + (r - mean_risk) * TEMPORAL_AMP)))
        for r in risk_values
    ]
    for h in range(24):
        hourly_risk.append({"hour": format_hour(h), "risk": amplified[h]})

    # Sliding 4-hour window for truly dynamic Peak/Safest extraction
    window_size = 4
    extended = risk_values + risk_values
    
    max_sum = -1
    peak_start = 0
    for i in range(24):
        w_sum = sum(extended[i:i+window_size])
        if w_sum > max_sum:
            max_sum = w_sum
            peak_start = i
            
    min_sum = 99999
    safe_start = 0
    for i in range(24):
        w_sum = sum(extended[i:i+window_size])
        if w_sum < min_sum:
            min_sum = w_sum
            safe_start = i

    def hour_range_label(start: int) -> str:
        end = (start + window_size - 1) % 24
        s_idx = start % 24
        def fmt(h):
            if h == 0: return "12 AM"
            elif h < 12: return f"{h} AM"
            elif h == 12: return "12 PM"
            else: return f"{h-12} PM"
        return f"{fmt(s_idx)} – {fmt(end)}"

    time_analysis = TimeAnalysis(
        currentRisk=risk_values[hour],
        peakHours=hour_range_label(peak_start),
        safestHours=hour_range_label(safe_start),
    )

    heatmap_points = compute_heatmap_from_incidents(city_incidents, req.lat, req.lng)

    emergency_numbers = get_emergency_numbers(state_abbr, city, country_code)

    # Include nearby user reports in heatmap
    for report in user_reports:
        dlat = abs(report["lat"] - req.lat)
        dlng = abs(report["lng"] - req.lng)
        if dlat < 0.05 and dlng < 0.05:
            heatmap_points.append({
                "lat": report["lat"],
                "lng": report["lng"],
                "weight": report["severity"] / 5.0,
                "type": report.get("category", "User Report"),
                "source": "User Report",
            })

    # ── Gemini heatmap enrichment (adds contextual descriptions to hover) ──
    heatmap_points = await gemini_enrich_heatmap(
        heatmap_points,
        city_name=city,
        state_abbr=state_abbr,
        crime_rate=crime_rate_per_100k,
        hour=hour,
        incident_types=incident_types,
        live_incident_summary=live_incident_summary,
    )

    nearby_pois = [NearbyPOI(**p) for p in pois]

    weather_info = WeatherInfo(
        condition=weather.get("owm_condition", "Clear"),
        description=weather.get("owm_description", ""),
        icon=weather.get("owm_icon", "01d"),
        temp_celsius=weather.get("temp_celsius"),
        humidity=weather.get("humidity"),
        wind_speed=weather.get("wind_speed"),
        alert_count=weather.get("alert_count", 0),
    )

    # ── Build live incident list for the response ──
    live_incident_models = []
    for inc in live_incidents:
        live_incident_models.append(LiveIncident(
            type=inc.get("type", "Unknown"),
            date=inc.get("date", ""),
            lat=inc.get("lat", 0.0) or 0.0,
            lng=inc.get("lng", 0.0) or 0.0,
            distance_miles=inc.get("distance_miles", 0.0) or 0.0,
            source=inc.get("source", ""),
            severity=inc.get("severity", ""),
            headline=inc.get("headline", ""),
        ))

    # ── Include Citizen incidents with epoch-ms → ISO conversion ──
    for inc in citizen_incidents:
        ts_ms = inc.get("ts") or inc.get("cs") or 0
        date_str = ""
        if ts_ms:
            try:
                date_str = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
            except (OSError, ValueError):
                pass
        dist = 0.0
        if inc.get("lat") and inc.get("lng"):
            dlat = inc["lat"] - req.lat
            dlng = inc["lng"] - req.lng
            dist = round(((dlat ** 2 + dlng ** 2) ** 0.5) * 69.0, 2)
        severity_map = {"red": "severe", "yellow": "moderate", "green": "minor", "grey": "minor"}
        live_incident_models.append(LiveIncident(
            type=inc.get("title", "Incident"),
            date=date_str,
            lat=inc.get("lat", 0.0),
            lng=inc.get("lng", 0.0),
            distance_miles=dist,
            source="Citizen",
            severity=severity_map.get(inc.get("severity", ""), "moderate"),
            headline=inc.get("title", ""),
        ))

    # ── Derive neighborhood context from scoring features ──
    ctx_parts = []
    if is_urban:
        ctx_parts.append("Urban area")
    else:
        ctx_parts.append("Suburban/rural area")
    if is_college:
        ctx_parts.append("near college campus")
    if poi_density > 0.5:
        ctx_parts.append("high foot traffic")
    elif poi_density > 0.2:
        ctx_parts.append("moderate foot traffic")
    if population > 0:
        ctx_parts.append(f"population ~{population:,}")
    neighborhood_context = ", ".join(ctx_parts)

    # ── Sentiment summary (GDELT + incident patterns) ──
    sentiment_summary = ""
    try:
        from sentiment import fetch_gdelt_news, analyze_incident_patterns, build_sentiment_summary
        gdelt_results = await fetch_gdelt_news(city, state_abbr)
        incident_analysis = analyze_incident_patterns(live_incidents)
        sentiment_summary = build_sentiment_summary(gdelt_results, incident_analysis, city)
    except Exception as e:
        logger.warning(f"Sentiment analysis skipped: {e}")

    return SafetyResponse(
        safetyIndex=safety_index,
        riskLevel=risk_level,
        incidentTypes=incident_types,
        timeAnalysis=time_analysis,
        dataSources=data_sources,
        hourlyRisk=[HourlyRisk(**h) for h in hourly_risk],
        heatmapPoints=[HeatmapPoint(**p) for p in heatmap_points],
        heatmapIncidentCount=total_annual_crime,
        emergencyNumbers=emergency_numbers,
        nearbyPOIs=nearby_pois,
        weather=weather_info,
        liveIncidents=live_incident_models,
        sentimentSummary=sentiment_summary,
        neighborhoodContext=neighborhood_context,
    )


# ─────────────────────────── Route Analysis ─────────────────────

@app.post("/api/route", response_model=RouteResponse)
async def get_route_safety(req: RouteRequest):
    """Analyze safety along a route.

    Key improvements over v2:
    - Fetches crime / weather / events for BOTH origin and destination
    - Interpolates data along intermediate segments
    - Advances the hour per-segment based on elapsed travel time
    - Passes full route duration (not per-segment fragment) for exposure penalty
    - Uses minimum-aware overall scoring so a single danger segment is not hidden
    - Returns rich data: incidentTypes, timeAnalysis, hourlyRisk, dataSources
    """
    directions = await fetch_route_directions(
        req.originLat, req.originLng,
        req.destLat, req.destLng,
        req.mode,
    )

    if not directions or not directions.get("points"):
        raise HTTPException(status_code=404, detail="Could not find route")

    points = directions["points"]
    try:
        hour = int(req.timeOfTravel.split(":")[0])
        if not (0 <= hour <= 23):
            hour = 12
    except (ValueError, IndexError):
        hour = 12

    # Parse duration into minutes
    total_duration_min = max(1, directions.get("duration_seconds", 1800) // 60)

    # ── Sample points along the route ───────────────────────────
    step = max(1, len(points) // 10)
    sample_points = points[::step]
    if points[-1] not in sample_points:
        sample_points.append(points[-1])
    n_segments = max(len(sample_points) - 1, 1)

    # ── Fetch data for BOTH origin AND destination in parallel ──
    origin_pt = sample_points[0]
    dest_pt = sample_points[-1]

    origin_state, dest_state, origin_city, dest_city = await asyncio.gather(
        fetch_state_from_coords(origin_pt[0], origin_pt[1]),
        fetch_state_from_coords(dest_pt[0], dest_pt[1]),
        reverse_geocode_city(origin_pt[0], origin_pt[1]),
        reverse_geocode_city(dest_pt[0], dest_pt[1]),
    )

    # Fetch full data for both endpoints
    (
        origin_fbi, origin_pop, origin_weather, origin_crime, origin_nibrs,
        origin_live_events, origin_live_incidents, origin_moon, origin_pois,
        origin_citizen,
        dest_fbi, dest_pop, dest_weather, dest_crime, dest_nibrs,
        dest_live_events, dest_live_incidents, dest_moon, dest_pois,
        dest_citizen,
    ) = await asyncio.gather(
        # Origin fetches
        fetch_fbi_crime_data(origin_state) if origin_state else _noop_dict(),
        fetch_census_population(origin_pt[0], origin_pt[1]),
        fetch_nws_weather(origin_pt[0], origin_pt[1]),
        fetch_city_crime_data(origin_pt[0], origin_pt[1], origin_city),
        fetch_fbi_nibrs_detail(origin_state) if origin_state else _noop_dict(),
        fetch_local_events(origin_pt[0], origin_pt[1]),
        fetch_live_incidents(origin_pt[0], origin_pt[1]),
        fetch_moon_illumination(origin_pt[0], origin_pt[1]),
        fetch_nearby_pois(origin_pt[0], origin_pt[1]),
        fetch_citizen_incidents(origin_pt[0], origin_pt[1]),
        # Destination fetches
        fetch_fbi_crime_data(dest_state) if dest_state else _noop_dict(),
        fetch_census_population(dest_pt[0], dest_pt[1]),
        fetch_nws_weather(dest_pt[0], dest_pt[1]),
        fetch_city_crime_data(dest_pt[0], dest_pt[1], dest_city),
        fetch_fbi_nibrs_detail(dest_state) if dest_state else _noop_dict(),
        fetch_local_events(dest_pt[0], dest_pt[1]),
        fetch_live_incidents(dest_pt[0], dest_pt[1]),
        fetch_moon_illumination(dest_pt[0], dest_pt[1]),
        fetch_nearby_pois(dest_pt[0], dest_pt[1]),
        fetch_citizen_incidents(dest_pt[0], dest_pt[1]),
    )

    # ── Helper: derive crime rate from FBI data ─────────────────
    def _crime_rate(fbi_data, population, city_name, city_crime_result, state_abbr):
        city_incidents = city_crime_result.get("incidents", [])
        total_annual = city_crime_result.get("total_annual_count", len(city_incidents))
        if fbi_data and fbi_data.get("population"):
            total_crime = fbi_data.get("violent_crime", 0) + fbi_data.get("property_crime", 0)
            state_rate = (total_crime / fbi_data["population"]) * 100_000
            return estimate_local_crime_rate(
                state_rate, population, city_name=city_name,
                city_incidents=city_incidents, total_annual_crime=total_annual,
                state_abbr=state_abbr,
            ), city_incidents, total_annual
        elif total_annual > 0 and population > 0:
            return min((total_annual / population) * 100_000, 8000), city_incidents, total_annual
        return 0.0, city_incidents, total_annual

    origin_rate, origin_incidents, origin_annual = _crime_rate(
        origin_fbi, origin_pop, origin_city, origin_crime, origin_state)
    dest_rate, dest_incidents, dest_annual = _crime_rate(
        dest_fbi, dest_pop, dest_city, dest_crime, dest_state)

    # Merge all incidents for density computation
    all_incidents = origin_incidents + [
        inc for inc in dest_incidents
        if inc not in origin_incidents  # rough dedup
    ]

    # Crime profiles for origin & destination
    origin_profile = get_state_crime_profile(origin_state, origin_fbi, origin_nibrs)
    dest_profile = get_state_crime_profile(dest_state, dest_fbi, dest_nibrs)

    # ── Incident density helper ─────────────────────────────────
    def _nearby_incident_density(lat: float, lng: float, incidents: list[dict], radius_deg: float = 0.01) -> int:
        count = 0
        for inc in incidents:
            try:
                ilat = float(inc.get("lat", 0))
                ilng = float(inc.get("lng", 0))
                if ilat == 0 or ilng == 0:
                    continue
                if abs(ilat - lat) < radius_deg and abs(ilng - lng) < radius_deg:
                    count += 1
            except (ValueError, TypeError):
                continue
        return count

    # Precompute segment densities
    segment_densities = []
    for i in range(n_segments):
        mid_lat = (sample_points[i][0] + sample_points[i + 1][0]) / 2
        mid_lng = (sample_points[i][1] + sample_points[i + 1][1]) / 2
        segment_densities.append(_nearby_incident_density(mid_lat, mid_lng, all_incidents))
    max_density = max(segment_densities) if segment_densities else 1

    # ── Build segments with per-segment safety scores ───────────
    segments = []
    segment_scores = []
    is_weekend = 1.0 if datetime.utcnow().weekday() >= 5 else 0.0
    minutes_per_segment = total_duration_min / n_segments

    for i in range(n_segments):
        start = sample_points[i]
        end = sample_points[i + 1]
        t = i / max(n_segments - 1, 1)  # interpolation factor 0..1

        # Advance hour based on elapsed travel time
        elapsed_min = i * minutes_per_segment
        segment_hour = (hour + int(elapsed_min) // 60) % 24

        # Interpolate crime rate between origin and destination
        seg_crime_rate = origin_rate * (1 - t) + dest_rate * t

        # Interpolate population
        seg_population = int(origin_pop * (1 - t) + dest_pop * t)

        # Interpolate weather severity
        origin_sev = origin_weather.get("max_severity", 0.0)
        dest_sev = dest_weather.get("max_severity", 0.0)
        seg_weather = origin_sev * (1 - t) + dest_sev * t

        # Select matching profile
        seg_profile = origin_profile if t < 0.5 else dest_profile
        seg_state = origin_state if t < 0.5 else dest_state
        seg_city = origin_city if t < 0.5 else dest_city

        # Interpolate live data
        seg_live_events = int(origin_live_events * (1 - t) + dest_live_events * t)
        seg_live_incidents_count = int(len(origin_live_incidents) * (1 - t) + len(dest_live_incidents) * t)
        seg_moon = origin_moon * (1 - t) + dest_moon * t

        # Local crime density variation
        if max_density > 0 and all_incidents:
            density_ratio = segment_densities[i] / max_density
            local_variation = 0.85 + density_ratio * 0.40
        else:
            rng = np.random.default_rng(abs(int(start[0] * 10000)) + abs(int(start[1] * 10000)))
            local_variation = rng.uniform(0.9, 1.1)

        # Dynamic location features
        city_lower = (seg_city or "").lower()
        is_college = 1.0 if any(k in city_lower for k in ["university", "college", "institute", "tech"]) else 0.0
        is_urban = 1.0 if seg_population > 250_000 else 0.0
        seg_pois = origin_pois if t < 0.5 else dest_pois
        poi_density = min(len(seg_pois) / 50.0, 1.0) if seg_pois else 0.0

        score, _ = compute_safety_score(
            seg_crime_rate * local_variation, segment_hour,
            req.peopleCount, req.gender,
            seg_weather, seg_population,
            all_incidents, safety_model,
            duration_minutes=total_duration_min,
            state_abbr=seg_state,
            crime_profile=seg_profile,
            is_college=is_college,
            is_urban=is_urban,
            is_weekend=is_weekend,
            poi_density=poi_density,
            lat=start[0],
            lng=start[1],
            live_events=seg_live_events,
            live_incidents=seg_live_incidents_count,
            moon_illumination=seg_moon,
            city_name=seg_city or "",
        )
        # Apply CIA — interpolate citizen incidents based on position along route
        seg_citizen = origin_citizen if t < 0.5 else dest_citizen
        seg_cia = compute_citizen_adjustment(
            target_lat=start[0], target_lng=start[1],
            citizen_incidents=seg_citizen,
            current_hour=hour,
            target_hour=segment_hour,
        )
        score = max(5, score - int(round(seg_cia)))
        segment_scores.append(score)
        risk = "safe" if score >= 70 else "caution" if score >= 40 else "danger"
        segments.append(RouteSegment(
            startLat=start[0], startLng=start[1],
            endLat=end[0], endLng=end[1],
            safetyScore=score, riskLevel=risk,
        ))

    # ── Minimum-aware overall scoring ───────────────────────────
    if segment_scores:
        mean_score = int(np.mean(segment_scores))
        min_score = int(min(segment_scores))
        # Don't let averaging hide a dangerous segment
        if min_score < 40:
            overall = min(mean_score, min_score + 10)
        else:
            overall = mean_score
    else:
        overall = 50

    # ── Gemini refinement on overall route score ────────────────
    _route_live_parts = []
    for inc in (origin_live_incidents + dest_live_incidents)[:8]:
        _route_live_parts.append(inc.get("type", "Unknown"))
    for inc in (origin_citizen + dest_citizen)[:8]:
        _sev_map = {"red": "severe", "yellow": "moderate", "green": "minor"}
        _route_live_parts.append(f"{inc.get('title', 'Incident')} ({_sev_map.get(inc.get('severity', ''), 'moderate')})")
    _route_live_summary = "; ".join(_route_live_parts[:12])
    _route_live_count = len(origin_live_incidents) + len(dest_live_incidents) + len(origin_citizen) + len(dest_citizen)

    overall = await gemini_refine_score(
        overall,
        city_name=origin_city,
        state_abbr=origin_state,
        hour=hour,
        crime_rate=origin_rate,
        weather_condition=origin_weather.get("owm_condition", "Clear"),
        weather_severity=max(origin_weather.get("max_severity", 0), dest_weather.get("max_severity", 0)),
        people_count=req.peopleCount,
        gender=req.gender,
        is_route=True,
        live_incident_summary=_route_live_summary,
        live_incident_count=_route_live_count,
    )
    overall_risk = "safe" if overall >= 70 else "caution" if overall >= 40 else "danger"

    # ── Warnings ────────────────────────────────────────────────
    warnings = []
    danger_segments = [s for s in segments if s.riskLevel == "danger"]
    caution_segments = [s for s in segments if s.riskLevel == "caution"]
    if danger_segments:
        warnings.append(f"{len(danger_segments)} segment(s) have elevated risk — consider alternate route.")
    if caution_segments and not danger_segments:
        warnings.append(f"{len(caution_segments)} segment(s) require caution.")
    if hour < 6 or hour >= 22:
        warnings.append("Late night travel — consider extra precautions.")
    max_weather = max(origin_weather.get("max_severity", 0), dest_weather.get("max_severity", 0))
    if max_weather > 0.5:
        warnings.append("Active weather alerts along the route.")
    if total_duration_min > 120:
        warnings.append(f"Long trip ({total_duration_min} min) — plan rest stops and stay aware.")
    if origin_state != dest_state and origin_state and dest_state:
        warnings.append(f"Route crosses state lines ({origin_state} → {dest_state}).")

    # ── Build rich response data ────────────────────────────────
    # Incident types from combined incidents
    incident_types = build_incident_types(
        all_incidents, origin_fbi, origin_rate,
        user_lat=origin_pt[0], user_lng=origin_pt[1],
        city_name=origin_city, state_abbr=origin_state,
        location=origin_city or "",
        hour=hour,
    )
    update_incident_crime_level(incident_types, overall)

    # Data sources
    data_sources = []
    if origin_fbi:
        data_sources.append(DataSource(
            name=f"FBI UCR ({origin_state or 'Origin'})",
            lastUpdated=f"{origin_fbi.get('year', 2023)}-12-31",
            recordCount=origin_fbi.get("record_count", 0),
        ))
    if dest_fbi and dest_state != origin_state:
        data_sources.append(DataSource(
            name=f"FBI UCR ({dest_state or 'Dest'})",
            lastUpdated=f"{dest_fbi.get('year', 2023)}-12-31",
            recordCount=dest_fbi.get("record_count", 0),
        ))
    if all_incidents:
        data_sources.append(DataSource(
            name="City Open Data Portals",
            lastUpdated=datetime.utcnow().strftime("%Y-%m-%d"),
            recordCount=len(all_incidents),
        ))
    data_sources.append(DataSource(
        name="U.S. Census Bureau",
        lastUpdated="2020-04-01",
        recordCount=origin_pop + dest_pop,
    ))

    # Time analysis — use departure hour analysis at origin
    hourly_risk = []
    risk_values = []

    def format_hour(h):
        h = h % 24
        if h == 0: return "12a"
        elif h < 12: return f"{h}a"
        elif h == 12: return "12p"
        else: return f"{h-12}p"

    for h in range(24):
        s_idx, _ = compute_safety_score(
            origin_rate, h, req.peopleCount, req.gender,
            origin_weather.get("max_severity", 0.0), origin_pop,
            origin_incidents, safety_model,
            duration_minutes=total_duration_min,
            state_abbr=origin_state,
            crime_profile=origin_profile,
            is_college=1.0 if any(k in (origin_city or "").lower() for k in ["university", "college"]) else 0.0,
            is_urban=1.0 if origin_pop > 250_000 else 0.0,
            is_weekend=is_weekend,
            poi_density=min(len(origin_pois) / 50.0, 1.0) if origin_pois else 0.0,
            lat=origin_pt[0], lng=origin_pt[1],
            live_events=origin_live_events,
            live_incidents=len(origin_live_incidents) + len(origin_citizen),
            moon_illumination=origin_moon,
            city_name=origin_city or "",
        )
        # Apply live-incident penalty with forecast decay for this hour
        h_cia = compute_citizen_adjustment(
            target_lat=origin_pt[0], target_lng=origin_pt[1],
            citizen_incidents=origin_citizen,
            current_hour=hour,
            target_hour=h,
        )
        s_idx = max(5, s_idx - int(round(h_cia)))
        risk_val = 100 - s_idx
        risk_values.append(risk_val)
        hourly_risk.append(HourlyRisk(hour=format_hour(h), risk=risk_val))

    # Peak / safest 4-hour window
    window_size = 4
    extended = risk_values + risk_values
    max_sum, peak_start = -1, 0
    min_sum, safe_start = 99999, 0
    for i in range(24):
        w_sum = sum(extended[i:i + window_size])
        if w_sum > max_sum:
            max_sum, peak_start = w_sum, i
        if w_sum < min_sum:
            min_sum, safe_start = w_sum, i

    def hour_range_label(start_h: int) -> str:
        end_h = (start_h + window_size - 1) % 24
        def fmt(h):
            if h == 0: return "12 AM"
            elif h < 12: return f"{h} AM"
            elif h == 12: return "12 PM"
            else: return f"{h-12} PM"
        return f"{fmt(start_h % 24)} – {fmt(end_h)}"

    time_analysis = TimeAnalysis(
        currentRisk=risk_values[hour],
        peakHours=hour_range_label(peak_start),
        safestHours=hour_range_label(safe_start),
    )

    return RouteResponse(
        overallSafety=overall,
        riskLevel=overall_risk,
        segments=segments,
        polyline=points,
        warnings=warnings,
        estimatedDuration=directions.get("duration", "Unknown"),
        estimatedDistance=directions.get("distance", "Unknown"),
        incidentTypes=incident_types,
        timeAnalysis=time_analysis,
        hourlyRisk=hourly_risk,
        dataSources=data_sources,
    )


# ─────────────────────────── Historical Trends ──────────────────

@app.get("/api/historical")
async def get_historical(state: str = "", lat: float = 0.0, lng: float = 0.0):
    """Get historical crime trends for the state."""
    if state:
        state_abbr = state.upper()
    elif lat and lng:
        state_abbr = await fetch_state_from_coords(lat, lng)
    else:
        raise HTTPException(status_code=400, detail="Provide 'state' or 'lat'+'lng' query params")
    data = await fetch_fbi_historical(state_abbr)

    if not data:
        return {"state": state_abbr, "data": [], "trend": "unknown"}

    # Determine trend
    if len(data) >= 3:
        recent = np.mean([d["ratePerCapita"] for d in data[-3:]])
        earlier = np.mean([d["ratePerCapita"] for d in data[:3]])
        if recent < earlier * 0.95:
            trend = "decreasing"
        elif recent > earlier * 1.05:
            trend = "increasing"
        else:
            trend = "stable"
    else:
        trend = "unknown"

    return {"state": state_abbr, "data": data, "trend": trend}


# ─────────────────────────── Nearby POIs ────────────────────────

@app.get("/api/nearby-pois")
async def get_nearby_pois(lat: float, lng: float):
    """Get nearby safety-relevant points of interest."""
    pois = await fetch_nearby_pois(lat, lng)
    return {"pois": pois}


# ─────────────────────────── User Reports ───────────────────────

@app.post("/api/reports", response_model=UserReportResponse)
async def submit_user_report(report: UserReport):
    """Submit a user safety report."""
    report_id = str(uuid.uuid4())[:8]
    user_reports.append({
        "id": report_id,
        "lat": report.lat,
        "lng": report.lng,
        "category": report.category,
        "description": report.description,
        "severity": report.severity,
        "timestamp": datetime.utcnow().isoformat(),
    })
    # Keep only last 1000 reports
    if len(user_reports) > 1000:
        user_reports.pop(0)

    logger.info(f"User report submitted: {report.category} at ({report.lat:.4f}, {report.lng:.4f})")
    return UserReportResponse(id=report_id, status="submitted")


@app.get("/api/reports")
async def get_user_reports(lat: float, lng: float, radius: float = 0.05):
    """Get user-submitted reports near a location."""
    nearby = []
    for r in user_reports:
        if abs(r["lat"] - lat) < radius and abs(r["lng"] - lng) < radius:
            nearby.append(r)
    return {"reports": nearby}


# ─────────────────────────── Utility Endpoints ──────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "model": "xgboost", "version": "4.0.0"}


@app.get("/api/geocode")
async def geocode(query: str):
    try:
        r = await client.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={"address": query, "key": GOOGLE_MAPS_API_KEY},
        )
        if r.status_code == 200:
            data = r.json()
            if data.get("status") == "OK" and data.get("results"):
                loc = data["results"][0]["geometry"]["location"]
                return {
                    "lat": loc["lat"],
                    "lng": loc["lng"],
                    "name": data["results"][0]["formatted_address"],
                }
    except Exception as e:
        logger.warning(f"Geocode error: {e}")
    raise HTTPException(status_code=404, detail="Location not found")


# ─────────────────────────── Citizen Hotspots ────────────────────

@app.get("/api/citizen-hotspots")
async def get_citizen_hotspots(
    lowerLatitude: float,
    lowerLongitude: float,
    upperLatitude: float,
    upperLongitude: float,
    limit: int = 200,
):
    """Proxy the unofficial Citizen trending-incidents API and normalise to HeatmapPoint[]."""
    try:
        r = await client.get(
            "https://citizen.com/api/incident/trending",
            params={
                "lowerLatitude": lowerLatitude,
                "lowerLongitude": lowerLongitude,
                "upperLatitude": upperLatitude,
                "upperLongitude": upperLongitude,
                "fullResponse": "true",
                "limit": limit,
            },
            timeout=10.0,
        )
        if r.status_code != 200:
            logger.warning(f"Citizen API returned {r.status_code}")
            return {"incidents": []}

        data = r.json()
        now_ms = time.time() * 1000
        cutoff_ms = now_ms - 24 * 60 * 60 * 1000

        incidents = []
        for item in data.get("results", []):
            ts = item.get("ts", 0) or item.get("cs", 0)
            if ts < cutoff_ms:
                continue
            lat = item.get("latitude")
            lng = item.get("longitude")
            if lat is None or lng is None:
                continue
            level = item.get("level", 1)
            date_str = ""
            if ts:
                try:
                    date_str = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
                except (OSError, ValueError):
                    pass
            incidents.append({
                "lat": lat,
                "lng": lng,
                "weight": max(level, 1) / 5.0,
                "type": item.get("title", "Incident"),
                "date": date_str,
                "source": "Citizen",
            })
        return {"incidents": incidents}
    except Exception as e:
        logger.warning(f"Citizen hotspots error: {e}")
        return {"incidents": []}


@app.get("/api/autocomplete")
async def autocomplete(query: str):
    try:
        r = await client.post(
            "https://places.googleapis.com/v1/places:autocomplete",
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,
            },
            json={
                "input": query,
                "languageCode": "en",
            },
        )
        if r.status_code == 200:
            data = r.json()
            suggestions = []
            for s in data.get("suggestions", []):
                place = s.get("placePrediction", {})
                suggestions.append({
                    "description": place.get("text", {}).get("text", ""),
                    "placeId": place.get("placeId", ""),
                })
            return {"suggestions": suggestions[:5]}
    except Exception as e:
        logger.warning(f"Autocomplete error: {e}")
    return {"suggestions": []}


# ─────────────────────────── AI Safety Tips (Gemini Proxy) ──────────────────────────

@app.post("/api/ai-tips")
async def ai_safety_tips(req: AISafetyTipsRequest):
    """Generate AI safety tips via Gemini, keeping the API key server-side."""
    if not GEMINI_API_KEY:
        return {"tips": _fallback_tips(req.safetyIndex, req.incidentTypes)}

    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")

        risk_label = 'generally safe' if req.safetyIndex >= 70 else 'moderate risk' if req.safetyIndex >= 40 else 'high risk'
        people_label = 'person' if req.peopleCount == 1 else 'people'

        # Build enriched context sections
        incidents_section = f"Common incidents nearby: {', '.join(req.incidentTypes)}" if req.incidentTypes else "Common incidents nearby: none reported"
        live_section = f"\nRecent live incidents (last 48h):\n{req.liveIncidentSummary}" if req.liveIncidentSummary else ""
        poi_section = f"\nNearby safety infrastructure: {', '.join(req.nearbyPOIs)}" if req.nearbyPOIs else ""
        neighborhood_section = f"\nNeighborhood type: {req.neighborhoodContext}" if req.neighborhoodContext else ""
        sentiment_section = f"\nCommunity & news sentiment: {req.sentimentSummary}" if req.sentimentSummary else ""

        prompt = f"""You are a public safety advisor AI. Given the following travel context, provide exactly 4 concise, actionable safety tips. Be specific to this neighborhood and its actual conditions — avoid generic advice.

Location: {req.locationName}
Safety Index: {req.safetyIndex}/100 ({risk_label})
{incidents_section}{live_section}{neighborhood_section}{poi_section}{sentiment_section}

Traveling at: {req.timeOfTravel}
Group size: {req.peopleCount} {people_label}
Gender: {req.gender}

Instructions:
- Reference specific conditions from the data above (e.g. if thefts are high, give theft-specific tips for this type of area)
- If there are active weather alerts, address them
- Tailor tips to the time of day and neighborhood character
- Be helpful and empowering, not fear-inducing

Return ONLY valid JSON — no markdown, no code fences:
[
  {{"title": "short title", "description": "1-2 sentence actionable tip specific to this area", "priority": "high|medium|low"}},
  ...
]"""

        result = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
            ),
        )
        text = result.text.strip()
        import json
        
        start_idx = text.find('[')
        end_idx = text.rfind(']')
        if start_idx != -1 and end_idx != -1:
            text = text[start_idx:end_idx+1]
            
        tips = json.loads(text)
        return {"tips": tips[:4]}

    except Exception as e:
        logger.warning(f"Gemini AI tips error: {e}")
        return {"tips": _fallback_tips(req.safetyIndex, req.incidentTypes)}


def _fallback_tips(safety_index: float, incident_types: list[str]) -> list[dict]:
    tips = [
        {"title": "Stay Aware of Surroundings", "description": "Keep your head up, phone away, and maintain awareness especially in unfamiliar areas.", "priority": "high"},
        {"title": "Share Your Location", "description": "Let someone you trust know your travel plans and share live location via your phone.", "priority": "medium"},
    ]
    if safety_index < 50:
        tips.append({"title": "Travel in Groups", "description": "This area has elevated risk. Traveling with others significantly reduces vulnerability.", "priority": "high"})
    if any("theft" in t.lower() for t in incident_types):
        tips.append({"title": "Secure Valuables", "description": "Keep bags zipped and close to your body. Avoid displaying expensive devices openly.", "priority": "medium"})
    if any("vehicle" in t.lower() or "auto" in t.lower() for t in incident_types):
        tips.append({"title": "Vehicle Safety", "description": "Don't leave valuables visible in your car. Park in well-lit, populated areas.", "priority": "medium"})
    if len(tips) < 4:
        tips.append({"title": "Know Emergency Exits", "description": "Identify nearby safe locations like police stations, hospitals, or well-lit businesses.", "priority": "low"})
    return tips[:4]


# ─────────────────────────── Safety Chat (Conversational Q&A) ──────────────────────────

@app.post("/api/safety-chat")
async def safety_chat(req: SafetyChatRequest):
    """Conversational safety Q&A powered by Gemini, with location context."""

    if not GEMINI_API_KEY:
        return {
            "reply": "I'm sorry, the AI chat service is currently unavailable. Please check back later.",
            "error": "no_api_key",
        }

    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        # Build location context block
        context_parts = []
        if req.locationName:
            context_parts.append(f"Location: {req.locationName}")
        if req.safetyIndex is not None:
            level = "generally safe" if req.safetyIndex >= 70 else "moderate risk" if req.safetyIndex >= 40 else "high risk"
            context_parts.append(f"Safety Index: {req.safetyIndex}/100 ({level})")
        if req.incidentTypes:
            context_parts.append(f"Common incidents nearby: {', '.join(req.incidentTypes)}")
        if req.riskLevel:
            context_parts.append(f"Risk Level: {req.riskLevel}")
        if req.timeOfTravel:
            context_parts.append(f"Time of travel: {req.timeOfTravel}")

        context_block = "\n".join(context_parts) if context_parts else "No specific location selected."

        system_prompt = f"""You are Lumos Safety Assistant, an expert public safety advisor embedded in a route-safety app. You help users make informed decisions about personal safety while traveling.

Current context:
{context_block}

Guidelines:
- Be concise (2-4 sentences per response unless the user asks for detail).
- Be helpful and informative, not fear-inducing.
- Base answers on the location context provided. If the user asks about a specific area and you have context, reference it.
- If you don't have enough context to answer accurately, say so honestly.
- You can discuss crime trends, safe travel tips, neighborhood safety, best times to travel, and emergency preparedness.
- Never provide medical, legal, or financial advice.
- Format responses in plain text (no markdown)."""

        model = genai.GenerativeModel(
            "gemini-2.0-flash",
            system_instruction=system_prompt,
        )

        # Build conversation for Gemini
        history = []
        for msg in req.conversationHistory[-10:]:
            role = "user" if msg.get("role") == "user" else "model"
            history.append({"role": role, "parts": [msg.get("content", "")]})

        chat = model.start_chat(history=history)
        result = chat.send_message(
            req.message,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=512,
            ),
        )

        return {"reply": result.text.strip(), "error": None}

    except Exception as e:
        logger.warning(f"Safety chat error: {e}")
        return {
            "reply": "I'm having trouble connecting right now. For immediate safety concerns, please call 911 or your local emergency number.",
            "error": "fallback",
        }
