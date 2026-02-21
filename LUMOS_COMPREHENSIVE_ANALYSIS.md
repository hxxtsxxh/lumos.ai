# LUMOS — Comprehensive Codebase Analysis & Strategic Roadmap

> **"Know Before You Go"** — A real-time location safety analytics platform  
> Hacklytics 2026 | Last Updated: February 21, 2026

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [Feature Inventory](#3-feature-inventory)
4. [Backend Deep Dive](#4-backend-deep-dive)
5. [Frontend Deep Dive](#5-frontend-deep-dive)
6. [Data Pipeline & Sources](#6-data-pipeline--sources)
7. [Machine Learning Model](#7-machine-learning-model)
8. [Integrations Map](#8-integrations-map)
9. [The Good — Strengths](#9-the-good--strengths)
10. [The Bad — Issues & Bugs](#10-the-bad--issues--bugs)
11. [The Ugly — Critical Weaknesses](#11-the-ugly--critical-weaknesses)
12. [Recommended Fixes (Priority-Ordered)](#12-recommended-fixes-priority-ordered)
13. [Potential New Features & Enhancements](#13-potential-new-features--enhancements)
14. [Hackathon Prize Strategy](#14-hackathon-prize-strategy)
15. [Technical Debt Summary](#15-technical-debt-summary)
16. [Appendix: File-by-File Reference](#16-appendix-file-by-file-reference)

---

## 1. Executive Summary

**Lumos** is a full-stack PWA that provides location-based safety analysis. Users enter an address or route, and the system aggregates data from **12+ external APIs** (FBI crime databases, Socrata open data portals for 30+ cities, NWS weather, Google Maps/Places/Routes, Ticketmaster events, AstronomyAPI moon data, Citizen.com live incidents, and Google Gemini AI) to produce a composite safety score (0–100), hourly risk curves, crime heatmaps, AI safety tips, nearby safe places, historical trends, and emergency resources.

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 18 + TypeScript + Vite + Tailwind CSS + shadcn/ui + Mapbox GL JS + Recharts + Framer Motion |
| **Backend** | Python FastAPI + httpx (async HTTP) + TensorFlow/Keras (ML) + Google Generative AI (Gemini) |
| **Auth/Storage** | Firebase Auth (Google SSO) + Firestore (saved reports) |
| **Data** | FBI CDE API, 30+ Socrata city portals, ArcGIS, CKAN, Carto, NWS, OpenWeatherMap, Census Bureau, Google Maps, Ticketmaster, AstronomyAPI, Citizen.com |
| **Deployment** | PWA with Service Worker, manual chunk splitting (Firebase + Mapbox bundles) |

**Lines of Code:**
- Backend Python: ~6,000+ lines across 13 files
- Frontend TypeScript/React: ~5,000+ lines across 25+ custom components
- Pre-computed datasets: ~70MB+ of JSON/CSV crime data

---

## 2. Architecture Overview

```
┌────────────────────────────────────────────────────────────────┐
│                        CLIENT (React PWA)                      │
│  ┌──────────┐ ┌────────────┐ ┌──────────┐ ┌──────────────┐   │
│  │ GlobeView│ │SearchBar   │ │Dashboard │ │ walkWithMe   │   │
│  │(Mapbox)  │ │(Autocomplete│ │(Score/   │ │(Geolocation  │   │
│  │Heatmaps  │ │ +Geocode)  │ │ Charts)  │ │ Tracking)    │   │
│  └────┬─────┘ └─────┬──────┘ └────┬─────┘ └──────┬───────┘   │
│       │              │             │               │           │
│  ┌────┴──────────────┴─────────────┴───────────────┴──────┐   │
│  │               Index.tsx (Page Controller)               │   │
│  │  State: appState, safetyData, locationCoords, params    │   │
│  └────────────────────────┬────────────────────────────────┘   │
│                           │                                    │
│  ┌──────────┐ ┌──────────┴──────────┐ ┌───────────────────┐   │
│  │ Firebase │ │   API Client Layer   │ │ Service Worker    │   │
│  │Auth+Store│ │  (src/lib/api.ts)    │ │ (Cache Strategy)  │   │
│  └──────────┘ └──────────┬──────────┘ └───────────────────┘   │
└──────────────────────────┼─────────────────────────────────────┘
                           │ HTTP (POST/GET)
┌──────────────────────────┼─────────────────────────────────────┐
│                    BACKEND (FastAPI)                            │
│  ┌───────────────────────┴────────────────────────────────┐    │
│  │                  routes.py (Endpoints)                  │    │
│  │  /api/safety  /api/route  /api/historical  /api/ai-tips│    │
│  │  /api/nearby-pois  /api/reports  /api/geocode          │    │
│  │  /api/citizen-hotspots  /api/autocomplete  /api/health │    │
│  └───┬──────────────┬──────────────┬──────────────┬───────┘    │
│      │              │              │              │             │
│  ┌───┴───┐   ┌──────┴──────┐  ┌───┴────┐  ┌─────┴──────┐     │
│  │scoring│   │data_fetchers│  │ml_model│  │nibrs_data  │     │
│  │.py    │   │.py (11 APIs)│  │.py     │  │.py         │     │
│  └───┬───┘   └──────┬──────┘  └───┬────┘  └─────┬──────┘     │
│      │              │              │              │             │
│  ┌───┴───┐   ┌──────┴──────┐  ┌───┴────┐  ┌─────┴──────┐     │
│  │Gemini │   │  TTL Cache  │  │Keras   │  │GA CSV Data │     │
│  │AI API │   │  (cache.py) │  │Model   │  │(2018-2024) │     │
│  └───────┘   └─────────────┘  └────────┘  └────────────┘     │
│                                                                │
│  ┌────────────────────────────────────────────────────────┐    │
│  │ Static Data: nationwide_data.py, city_crime_loader.py, │    │
│  │ fbi_cde_loader.py, collect_state_data.py               │    │
│  └────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────┘
```

### Request Flow (Single Location)

```
User types address
  → Google Maps Geocoding (client-side) → lat/lng
  → POST /api/safety { lat, lng, params }
    → Reverse geocode (city, state, country) [3 Google API calls]
    → asyncio.gather() [10 parallel data fetches]:
        1. FBI CDE state crime data
        2. City-level crime data (Socrata/ArcGIS/CKAN/Carto)
        3. NWS + OpenWeatherMap weather
        4. Census population
        5. Country code
        6. Nearby POIs (Google Places)
        7. FBI NIBRS detail
        8. Live incidents (Socrata recent + NWS alerts)
        9. Local events (Ticketmaster)
        10. Moon illumination (AstronomyAPI)
    → Estimate local crime rate
    → Build incident types (4-tier fallback)
    → Compute safety score (formula × 0.85 + ML × 0.15)
    → Gemini AI score refinement (±15 points)
    → Generate hourly risk curve (24h)
    → Generate heatmap (real + synthetic points)
    → Gemini heatmap enrichment
    → Build response JSON
  → Client receives FullSafetyResponse
    → Render dashboard panels
    → Add Mapbox heatmap/marker/POI layers
    → Fetch Citizen.com incidents (separate call)
```

---

## 3. Feature Inventory

### Core Features

| # | Feature | Status | Quality |
|---|---------|--------|---------|
| 1 | **Single Location Safety Analysis** | ✅ Working | ⭐⭐⭐⭐ Solid |
| 2 | **Route Safety Analysis** (A→B) | ✅ Working | ⭐⭐⭐ Good |
| 3 | **Interactive 3D Globe** (Mapbox) | ✅ Working | ⭐⭐⭐⭐⭐ Excellent |
| 4 | **Crime Heatmap Visualization** | ✅ Working | ⭐⭐⭐⭐ Good |
| 5 | **Live Incident Heatmap** (Citizen.com) | ✅ Working | ⭐⭐⭐ Depends on API |
| 6 | **AI Safety Tips** (Gemini) | ✅ Working | ⭐⭐⭐⭐ Good |
| 7 | **Hourly Risk Chart** (24h curve) | ✅ Working | ⭐⭐⭐⭐ Good |
| 8 | **Historical Crime Trends** (multi-year) | ✅ Working | ⭐⭐⭐ Good |
| 9 | **Nearby Safe Places** (POIs) | ✅ Working | ⭐⭐⭐⭐ Good |
| 10 | **Emergency Resources** (phone numbers) | ✅ Working | ⭐⭐⭐ Adequate |
| 11 | **Walk With Me** (real-time tracker) | ✅ Working | ⭐⭐⭐⭐ Great feature |
| 12 | **Community Incident Reports** | ✅ Working | ⭐⭐ In-memory only |
| 13 | **Dark/Light Theme Toggle** | ✅ Working | ⭐⭐⭐⭐⭐ Excellent |
| 14 | **Google Auth + Saved Reports** | ✅ Working | ⭐⭐⭐⭐ Good |
| 15 | **Export Report** (txt file) | ✅ Working | ⭐⭐⭐ Functional |
| 16 | **Share Report** (Web Share API) | ✅ Working | ⭐⭐⭐ Functional |
| 17 | **Search Autocomplete** | ✅ Working | ⭐⭐⭐⭐ Good UX |
| 18 | **PWA Support** (offline, installable) | ✅ Working | ⭐⭐⭐ Basic |
| 19 | **Travel Parameter Customization** | ✅ Working | ⭐⭐⭐⭐ Good |
| 20 | **URL Deep Linking** | ✅ Working | ⭐⭐⭐ Functional |
| 21 | **ML Safety Prediction** | ⚠️ Partial | ⭐⭐ Circular training |
| 22 | **Rate Limiting** | ✅ Working | ⭐⭐ Basic IP-based |
| 23 | **Multi-source Data Aggregation** | ✅ Working | ⭐⭐⭐⭐ Impressive |
| 24 | **Keyboard Shortcuts** (/, Esc) | ✅ Working | ⭐⭐⭐ Minimal |

### Data Sources Integrated

| # | Source | Type | Coverage |
|---|--------|------|----------|
| 1 | FBI Crime Data Explorer (CDE) | Federal API | All 50 states + DC |
| 2 | Socrata Open Data | City APIs | 30+ major cities |
| 3 | ArcGIS REST | City APIs | DC, select cities |
| 4 | CKAN | City APIs | Boston |
| 5 | Carto SQL | City APIs | Philadelphia |
| 6 | National Weather Service | Federal API | US nationwide |
| 7 | OpenWeatherMap | Commercial API | Global |
| 8 | US Census Bureau | Federal API | US nationwide |
| 9 | Google Maps/Places/Routes | Commercial API | Global |
| 10 | Ticketmaster Discovery | Commercial API | US + International |
| 11 | AstronomyAPI | Commercial API | Global |
| 12 | Citizen.com | Unofficial API | Major US cities |
| 13 | Google Gemini 2.5 Flash | AI API | Global |
| 14 | FBI UCR Tables 8/9/10 | Pre-downloaded JSON | US nationwide |
| 15 | Georgia NIBRS CSV | Pre-downloaded CSV | Georgia (2018-2024) |

---

## 4. Backend Deep Dive

### 4.1 Endpoint Analysis

#### `POST /api/safety` — Main Safety Analysis
- **Input:** lat, lng, peopleCount, gender, timeOfTravel, duration, locationName
- **Processing time:** 2-8 seconds (10+ parallel API calls + Gemini)
- **Output:** SafetyResponse with score (0-100), incidents, heatmap, hourly risk, POIs, emergency numbers, data sources

**Scoring Formula:**
```
base_risk = 50 × (crime_rate / us_avg_rate)
adjustments = time_factor × group_factor × gender_factor × weather_factor 
              × duration_factor × event_factor × incident_factor × moon_factor
formula_score = clamp(100 - adjusted_risk, 0, 100)
ml_score = neural_network.predict(15 features)
final_score = formula_score × 0.85 + ml_score × 0.15
gemini_refined = final_score ± 15 (AI adjustment)
```

**15 ML Features:**
1. crime_rate_per_100k
2. hour_sin (cyclical)
3. hour_cos (cyclical)
4. is_weekend
5. violent_crime_rate
6. property_crime_rate
7. gender_factor
8. people_count
9. weather_severity
10. event_density
11. live_incident_count
12. poi_density
13. moon_illumination
14. is_college
15. population_density

#### `POST /api/route` — Route Safety
- Fetches Google Routes API for polyline
- Splits into segments at regular intervals
- Computes safety score per segment
- Color-codes route visualization (green/yellow/red)

#### `GET /api/historical` — Historical Trends
- Returns multi-year crime data by state
- Sources: FBI CDE pre-downloaded JSON + API

#### `POST /api/ai-tips` — AI Safety Tips
- Sends location context to Gemini 2.5 Flash
- Returns structured JSON tips with priority levels
- Hardcoded fallback tips when Gemini is unavailable

### 4.2 Safety Scoring Breakdown

The scoring system uses a **multi-factor formula blended with ML prediction**:

| Factor | Weight/Impact | Description |
|--------|--------------|-------------|
| Crime Rate | Base (×1.0) | Local crime rate vs. national average |
| Time of Day | ×0.7–1.5 | Higher risk at night (10pm–5am), lowest midday |
| Group Size | ×0.6–1.0 | More people = safer (1 person = 1.0, 4+ = 0.6) |
| Gender | ×0.85–1.0 | Female solo = higher risk, mixed groups = moderate |
| Weather | ×0.9–1.0 | Poor weather slightly increases risk |
| Duration | ×1.0–1.4 | Longer exposure = higher risk |
| Events | ×0.95–1.15 | Large events increase risk |
| Live Incidents | ×1.0–1.25 | Active nearby incidents increase risk |
| Moon Phase | ×0.97–1.05 | Full moon = slightly higher risk |
| ML Model | 15% blend | Neural network prediction |
| Gemini AI | ±15 points | Contextual refinement |

### 4.3 Caching Strategy

| Cache | TTL | Max Size | Purpose |
|-------|-----|----------|---------|
| `fbi_cache` | 24 hours | 500 | FBI CDE API responses |
| `city_cache` | 30 minutes | 500 | Socrata city crime data |
| `weather_cache` | 15 minutes | 500 | NWS + OpenWeatherMap |
| `census_cache` | 7 days | 500 | Census population |
| `state_cache` | 7 days | 500 | State reverse geocode |
| `poi_cache` | 24 hours | 500 | Google Places nearby |
| `historical_cache` | 24 hours | 500 | Historical trends |
| `_ML_LRU_CACHE` | — | 10,000 | ML predictions (LRU) |
| `_GEMINI_CACHE` | — | 128 | Gemini score refinements |
| `_HEATMAP_GEMINI_CACHE` | — | 64 | Gemini heatmap descriptions |

---

## 5. Frontend Deep Dive

### 5.1 Component Architecture

**Page structure:** Single-page application with one route (`/`). The entire UI lives in `Index.tsx` (932 lines), which acts as the controller for:
- **27 state variables** managing the entire app state
- 3 app states: `landing` → `loading` → `results`
- 2 search modes: `single` and `route`

**Component tree (results view):**
```
Index.tsx
├── Header Bar
│   ├── LumosLogo (click → reset to globe)
│   ├── ThemeToggle
│   ├── Heatmap Toggle Buttons
│   ├── Save / Export / Share Buttons
│   ├── "New Search" Button
│   └── UserMenu (Auth + Saved Reports)
│
├── Left Panel (380-420px)
│   ├── RouteSearchBar (minimized)
│   ├── ParameterPanel (travel settings)
│   ├── Refresh Button (if params changed)
│   └── HourlyRiskChart (single mode only)
│
├── Center (full viewport behind panels)
│   └── GlobeView (Mapbox GL)
│       ├── Crime Heatmap Layer
│       ├── Citizen Incident Heatmap Layer
│       ├── POI Markers
│       ├── Center Marker (amber pulse)
│       ├── User Location Marker (teal, Walk mode)
│       └── Route Segments (color-coded polylines)
│
├── Right Panel (360-380px, scrollable)
│   ├── SafetyDashboard (score, incidents, time, sources)
│   ├── AISafetyTips (Gemini-powered)
│   ├── NearbyPOIs (police, hospital, fire)
│   ├── HistoricalTrends (line chart)
│   ├── EmergencyResources (phone links)
│   ├── ReportIncident (community form)
│   └── RouteSafetyPanel (route mode only)
│
├── Bottom Sheet
│   └── WalkWithMe (live tracking companion)
│
└── Drawer
    └── SavedReportsPanel (Firestore reports)
```

### 5.2 Map & Visualization Features

**Globe:**
- 3D globe projection with atmospheric fog and stars (dark mode)
- Auto-rotation (0.0012°/ms) that pauses on interaction or zoom > 3
- Smooth fly-to animation (zoom 14, pitch 50°, cubic easing)
- Theme-reactive: swaps Mapbox styles and fog settings

**Heatmaps:**
- Crime heatmap: green → yellow → red gradient with density-based opacity
- Citizen heatmap: purple → fuchsia → rose gradient
- Interactive: hover to see incident details via Mapbox popups
- Zoom-responsive radius (15px → 30px)

**Route visualization:**
- Color-coded segmented polylines (green = safe, yellow = caution, red = danger)
- Outline layer for contrast
- Follows actual road geometry from Google Routes API

### 5.3 UX Features

- **Glassmorphism UI** — backdrop-blur panels with glass effects
- **Google-style search bar** — floating, animated focus/expand states
- **Autocomplete** — debounced (300ms) suggestions via Google Places
- **Mode switching** — smooth toggle between single location and route analysis
- **Parameter customization** — people count, gender, time, duration, travel mode
- **Keyboard shortcuts** — `/` focuses search, `Esc` returns to globe
- **Deep linking** — `?lat=&lng=&q=` URL params for sharing
- **PWA** — installable, offline-capable with service worker caching
- **Responsive design** — panels adapt (though primarily desktop-optimized)

### 5.4 Auth & Persistence

- **Firebase Auth** — Google Sign-In popup
- **Firestore** — `saved_reports` collection with `userId`, `locationName`, `coords`, `safetyData`, `params`, `timestamp`
- **UserMenu** — avatar display, saved reports access, sign out
- **SavedReportsPanel** — drawer listing all saved reports with load/delete actions

---

## 6. Data Pipeline & Sources

### 6.1 Crime Data Resolution Priority

```
1. Socrata City Open Data (real-time incidents, 30+ cities)
   ↓ fallback
2. FBI UCR Table 8/9/10 pre-downloaded JSON (city/college/county)
   ↓ fallback
3. FBI CDE API (state-level, current year)
   ↓ fallback
4. Hardcoded nationwide_data.py (2022 baseline, 50 states + 40 cities)
```

### 6.2 NIBRS (National Incident-Based Reporting System)

- **Georgia:** Full incident-level CSV data for 2018–2024 (~7 years)
  - Hourly crime distributions
  - Offense severity weighting
  - Weapon involvement rates
  - Victim demographics
  - Location-type risk factors
  - Agency-level crime rates
- **All other states:** Synthetic profiles derived from FBI CDE data + BJS research hourly patterns (8 crime-type-specific distribution curves)

### 6.3 Pre-Computed Datasets

| File | Size/Records | Content |
|------|-------------|---------|
| `city_crime_lookup.json` | ~8,986 cities | FBI UCR Table 8 (2024) |
| `college_crime_lookup.json` | ~1,600 institutions | FBI UCR Table 9 (2024) |
| `county_crime_lookup.json` | ~3,000 counties | FBI UCR Table 10 (2024) |
| `training_data.json` | ~15,000+ records | ML training vectors |
| `us_municipal_vectors_v2.json` | ~10,000+ cities | Pre-generated 15D feature vectors |
| `GA-2018/ through GA-2024/` | Millions of rows | Georgia NIBRS incident CSVs |
| `fbi_cde/` subdirectories | 50+ states × 6 years | Pre-downloaded FBI CDE responses |

### 6.4 Socrata City Coverage (30+ Cities)

Chicago, Los Angeles, New York, San Francisco, Austin, Seattle, Denver, Portland, Nashville, Dallas, Atlanta, Detroit, Baltimore, Philadelphia, Minneapolis, Milwaukee, Kansas City, Louisville, St. Louis, Memphis, Cleveland, Cincinnati, Columbus, Indianapolis, Jacksonville, Virginia Beach, Charlotte, Raleigh, Durham, Pittsburgh, Tampa, Washington DC (ArcGIS), Boston (CKAN), and dynamically discovered via ODN scraping.

---

## 7. Machine Learning Model

### 7.1 Architecture

```
Input (15 features)
  → Dense(256, ReLU, L2=0.001) → BatchNorm → Dropout(0.3)
  → Dense(128, ReLU, L2=0.001) → BatchNorm → Dropout(0.2)
  → Dense(64, ReLU)
  → Dense(32, ReLU)
  → Dense(1, Sigmoid) → output × 100 = safety_score
```

**Training:**
- ~15,000+ training vectors from 5 sources:
  1. FBI CDE state-year records (~300)
  2. Hardcoded nationwide data (~91 records — 51 states + 40 cities)
  3. UCR city/college/county lookups (~12,000+)
  4. Scraped Socrata city datasets
  5. Georgia NIBRS hourly augmentation
  6. Pre-generated municipal vectors (~10,000+)
- 70/15/15 train/val/test split
- Synthetic augmentation: ±20% noise on features
- Optimizer: Adam (lr=0.001), MSE loss, 100 epochs, early stopping (patience=15)

### 7.2 Critical Issue: Circular Training

The model's training labels are **generated by the same formula** that the model is blended with:
```
Training label = formula_score(crime_rate, hour, weather, gender, ...)
Final prediction = formula_score × 0.85 + model.predict() × 0.15
```

This means the ML model is essentially learning to replicate the formula with 15% weight. The `_FallbackModel` that returns a constant `0.7` (70/100) achieves nearly equivalent results because the formula dominates at 85%.

### 7.3 What the Model Could Be

With real ground-truth labels (actual crime outcomes, victim surveys, or validated safety rankings), the model could genuinely learn non-linear patterns the formula misses. Current architecture is sound — the problem is data labeling, not model design.

---

## 8. Integrations Map

```
┌──────────────────────────── EXTERNAL APIS ────────────────────────────┐
│                                                                       │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │ FBI CDE API │  │ Socrata Open │  │ Google Maps  │  │  Gemini   │ │
│  │ (state data)│  │ Data (30+    │  │ Geocoding    │  │ 2.5 Flash │ │
│  │             │  │  cities)     │  │ Places       │  │ (AI tips, │ │
│  │             │  │              │  │ Routes v2    │  │  scoring) │ │
│  └──────┬──────┘  └──────┬───────┘  └──────┬───────┘  └─────┬─────┘ │
│         │                │                 │                 │        │
│  ┌──────┴──────┐  ┌──────┴───────┐  ┌──────┴───────┐  ┌─────┴─────┐ │
│  │  NWS API   │  │ ArcGIS REST  │  │ Ticketmaster │  │ Astronomy │ │
│  │ + OpenWM   │  │ CKAN, Carto  │  │  Discovery   │  │    API    │ │
│  │ (weather)  │  │ (alt. cities)│  │  (events)    │  │  (moon)   │ │
│  └──────┬──────┘  └──────┬───────┘  └──────┬───────┘  └─────┬─────┘ │
│         │                │                 │                 │        │
│  ┌──────┴──────┐  ┌──────┴───────┐  ┌──────┴───────┐               │
│  │ Census API │  │ Citizen.com  │  │ Firebase     │               │
│  │(population)│  │ (unofficial  │  │ Auth +       │               │
│  │            │  │  live feed)  │  │ Firestore    │               │
│  └─────────────┘  └──────────────┘  └──────────────┘               │
│                                                                       │
│  CLIENT-SIDE:  Mapbox GL JS (tiles, 3D globe, layers)                │
│                Google Maps Geocoding (primary geocoder)                │
│                Mapbox Geocoding (fallback geocoder)                    │
└───────────────────────────────────────────────────────────────────────┘
```

---

## 9. The Good — Strengths

### 9.1 Impressive Data Aggregation
- **12+ external data sources** aggregated in parallel — one of the most comprehensive safety data pipelines seen in a hackathon project
- Multi-tier fallback chain ensures data is always available even when APIs fail
- Covers city-level, state-level, and national-level crime data with automatic resolution

### 9.2 Visual Excellence
- **3D interactive globe** with smooth auto-rotation and fly-to animations is visually stunning
- Dual heatmap layers (crime + live incidents) with distinct color palettes
- Glassmorphism UI design is modern and polished
- Dark/light theme with full Mapbox style synchronization
- Color-coded route segments provide intuitive at-a-glance safety assessment
- Custom SVG logo and cohesive amber + navy brand identity

### 9.3 Feature Depth
- **Walk With Me** real-time companion tracker is a standout feature
- Hourly risk curves provide temporal safety intelligence
- Historical multi-year trend charts show crime trajectory
- AI-powered safety tips add contextual, actionable advice
- Route analysis with per-segment scoring
- Community incident reporting system
- Export/share/save report functionality

### 9.4 Technical Quality
- Proper use of `asyncio.gather()` for parallel API fetching
- TTL-based caching with LRU eviction at multiple levels
- ML model with lazy-loading proxy pattern (graceful fallback)
- Service worker with sophisticated cache strategies (network-first for APIs, cache-first for assets, stale-while-revalidate for pages)
- Code splitting with manual chunks for Firebase and Mapbox
- Pydantic models for API request/response validation
- Type safety throughout the frontend (TypeScript)
- PWA manifest with maskable icons

### 9.5 Thoughtful Details
- Moon illumination as a safety factor (research-backed)
- Gender and group size adjustments
- Duration-based risk scaling
- College campus detection
- Non-emergency phone numbers for 13 major cities
- International emergency numbers (10 countries)
- BJS-derived hourly patterns for all 50 states

### 9.6 User Experience
- Google-style floating search with autocomplete
- Keyboard shortcuts (/ and Esc)
- URL deep linking for sharing
- "Use my location" quick action
- Destination quick picks (Restaurant, Coffee shop, etc.)
- Animated transitions with Framer Motion
- Toast notifications for user feedback

---

## 10. The Bad — Issues & Bugs

### 10.1 Backend Issues

#### Data Quality
| # | Issue | Severity | Location |
|---|-------|----------|----------|
| B1 | Only Georgia has real NIBRS incident-level data; all other states use synthetic BJS-derived profiles | High | nibrs_data.py |
| B2 | County population is estimated from crime volume (3,500 crimes per 100K heuristic) — unreliable | Medium | ml_model.py |
| B3 | Hardcoded 2022 nationwide data with no auto-update mechanism | Medium | nationwide_data.py |
| B4 | Synthetic heatmap points fabricate crime locations around POIs — potentially misleading | High | scoring.py |
| B5 | Moon illumination fallback uses Jan 25, 2024 reference — degrades over time | Low | data_fetchers.py |
| B6 | City fuzzy matching returns wrong city (e.g., "Springfield" resolves to largest population match) | Medium | city_crime_loader.py |
| B7 | College fuzzy match is too loose — "Georgia" matches "Georgia Institute of Technology" | Medium | city_crime_loader.py |

#### API & Integration
| # | Issue | Severity | Location |
|---|-------|----------|----------|
| B8 | Three separate Google reverse geocode calls per request (state, city, country) — should be one | Medium | data_fetchers.py |
| B9 | Citizen.com uses unofficial API — could break at any time | Medium | routes.py |
| B10 | FBI SAPI endpoints (victims, weapons) return 403/503 — documented as broken | High | collect_state_data.py |
| B11 | `httpx.AsyncClient` is never closed — resource leak | Medium | data_fetchers.py |
| B12 | ODN discovery scrapes HTML with regex — extremely brittle | Medium | data_fetchers.py |
| B13 | No input validation on lat/lng ranges — lat=999 will call all APIs | High | models.py, routes.py |
| B14 | Crimeometer API key configured but never used | Low | config.py |
| B15 | scikit-learn and xgboost in requirements but never imported | Low | requirements.txt |

#### Code Quality
| # | Issue | Severity | Location |
|---|-------|----------|----------|
| B16 | `format_hour()` and `hour_range_label()` defined as nested functions twice (duplicated) | Low | routes.py |
| B17 | `datetime.utcnow()` deprecated in Python 3.12+ | Low | routes.py |
| B18 | `asyncio.get_event_loop()` deprecated in Python 3.10+ | Low | collect_state_data.py |
| B19 | `@app.on_event("startup")` deprecated in newer FastAPI | Low | routes.py |
| B20 | ML model prediction under threading lock blocks async event loop | Medium | scoring.py |
| B21 | Gemini API key configured on every call — race condition risk | Medium | scoring.py |
| B22 | No dependency version pinning in requirements.txt | Medium | requirements.txt |

#### Architecture
| # | Issue | Severity | Location |
|---|-------|----------|----------|
| B23 | In-memory `user_reports` list — lost on restart, O(n) eviction with `pop(0)` | High | routes.py |
| B24 | Single-process only — caches, rate limiter, reports don't share across workers | High | Architecture |
| B25 | No backend tests | High | Architecture |
| B26 | Route endpoint computes 24 × n_segments ML inferences — O(segments × 24) | Medium | routes.py |
| B27 | No database — everything is in-memory or flat files | High | Architecture |
| B28 | No authentication on any endpoint | Medium | routes.py |
| B29 | ML model trained on formula-generated labels (circular dependency) | High | ml_model.py |

### 10.2 Frontend Issues

#### Bugs
| # | Issue | Severity | Location |
|---|-------|----------|----------|
| F1 | Firebase init with empty config crashes without try/catch | High | lib/firebase.ts |
| F2 | Memory leak — heatmap popup handlers never properly removed (new function refs) | Medium | Index.tsx |
| F3 | `useEffect` missing dependency (`onChange`, `params`) in ParameterPanel | Medium | ParameterPanel.tsx |
| F4 | `useEffect` missing dependency (`mode`) in RouteSearchBar | Low | RouteSearchBar.tsx |
| F5 | `defaultSuggestions` is empty — "Popular cities" dropdown is dead code | Low | RouteSearchBar.tsx |
| F6 | Autocomplete lacks request cancellation (AbortController) — stale responses | Medium | RouteSearchBar.tsx |
| F7 | `setTimeout(200ms)` onBlur race condition — fragile | Low | RouteSearchBar.tsx |

#### Architecture
| # | Issue | Severity | Location |
|---|-------|----------|----------|
| F8 | Index.tsx is 932 lines — God component with 27 state variables | High | pages/Index.tsx |
| F9 | No lazy loading / code splitting for pages | Medium | App.tsx |
| F10 | ~40 unused shadcn/ui component packages bloating node_modules | Low | package.json |
| F11 | Module-level mutable state in heatmap.ts (5 `let` variables) | Medium | lib/heatmap.ts |
| F12 | Multiple Mapbox Popup instances accumulate in memory | Medium | lib/heatmap.ts |
| F13 | No React.memo on chart components — cascade re-renders | Medium | Components |
| F14 | Service worker caches all API GETs permanently — no TTL eviction | Medium | public/sw.js |

#### Accessibility
| # | Issue | Severity | Location |
|---|-------|----------|----------|
| F15 | Heatmap data not keyboard-accessible (hover only) | High | Index.tsx, heatmap.ts |
| F16 | No skip-to-content link | Medium | App.tsx |
| F17 | Color-only risk indicators without text alternatives | Medium | RouteSafetyPanel.tsx |
| F18 | Map canvas has no aria-label | Medium | GlobeView.tsx |
| F19 | Search autocomplete lacks keyboard navigation (arrow keys) | Medium | RouteSearchBar.tsx |
| F20 | WalkWithMe bottom sheet has no focus trap | Low | WalkWithMe.tsx |

---

## 11. The Ugly — Critical Weaknesses

### 11.1 The ML Model is Essentially a No-Op

The most critical architectural issue: the ML model is trained on labels generated by the **same formula** it's blended with. At 15% weight, with a fallback constant of 0.7, removing the ML model entirely would change scores by < 5 points on average. The Keras neural network (5 layers, 256 parameters, TensorFlow dependency, startup training cost) adds computational overhead for negligible predictive value.

**Fix:** Either (a) remove the ML model and use formula-only with Gemini refinement, or (b) acquire real ground-truth safety labels (validated crime outcome data, safety rankings) and retrain.

### 11.2 Synthetic Data Masquerading as Real

`generate_synthetic_heatmap()` fabricates crime incident points anchored around POIs (police stations, hospitals). Users see these on the map and have no way to distinguish synthetic points from real incidents. This could erode trust if discovered.

**Fix:** Clearly label synthetic points or remove them. Only show real incident data from Socrata/Citizen.com.

### 11.3 Georgia Bias in NIBRS Data

Only Georgia has 7 years of real incident-level NIBRS CSV data. All other states use BJS-derived synthetic hourly distributions. This means hourly risk curves for Georgia are data-driven while other states get generic academic patterns.

**Fix:** Download NIBRS data for more states from the FBI's NIBRS data portal (data is publicly available for all participating states).

### 11.4 No Persistence Layer

User reports, rate limiting state, and API caches are all in-memory. A simple server restart wipes everything. This makes community incident reports worthless in production and prevents horizontal scaling.

**Fix:** Add Redis for caching/rate limiting, PostgreSQL or Firestore for persistent storage.

### 11.5 API Key Exposure Risk

The Gemini API key uses the frontend naming convention (`VITE_GEMINI_API_KEY`). While it's only used server-side, the VITE prefix convention could lead to accidental client-side bundling. Google Maps API key IS exposed client-side (necessary but should be restricted).

**Fix:** Rename backend keys without `VITE_` prefix. Configure API key restrictions in Google Cloud Console.

---

## 12. Recommended Fixes (Priority-Ordered)

### P0: Critical (Do before demo)

| # | Fix | Effort | Impact |
|---|-----|--------|--------|
| 1 | **Add lat/lng validation** in Pydantic models (`-90≤lat≤90`, `-180≤lng≤180`) | 5 min | Prevents crashes from invalid input |
| 2 | **Consolidate 3 Google reverse geocode calls into 1** — extract city, state, country from single response | 30 min | 3× faster response, lower API costs |
| 3 | **Add try/catch around Firebase initialization** | 5 min | Prevents crash when env vars missing |
| 4 | **Label synthetic heatmap points** — add `synthetic: true` flag and visual distinction | 15 min | Prevents misleading users |
| 5 | **Close httpx.AsyncClient** on shutdown | 5 min | Prevents resource leak |

### P1: High Priority (Improve quality)

| # | Fix | Effort | Impact |
|---|-----|--------|--------|
| 6 | **Decompose Index.tsx** into custom hooks (`useSafetyAnalysis`, `useMapManager`, `useRouteAnalysis`) | 2 hr | Maintainability, testability |
| 7 | **Pin dependency versions** in requirements.txt | 10 min | Reproducible builds |
| 8 | **Move user reports to Firestore** (backend already has Firebase configured client-side) | 1 hr | Persistence across restarts |
| 9 | **Add AbortController** to autocomplete fetches | 15 min | Prevent stale responses |
| 10 | **Add `React.memo`** to chart components and dashboard panels | 30 min | Performance improvement |
| 11 | **Remove unused npm packages** (40+ shadcn/ui unused) | 15 min | Smaller bundle |
| 12 | **Remove scikit-learn, xgboost, orjson** from requirements.txt | 5 min | Cleaner dependencies |

### P2: Medium Priority (Polish)

| # | Fix | Effort | Impact |
|---|-----|--------|--------|
| 13 | Extract duplicate `format_hour()` functions to module level | 10 min | Code quality |
| 14 | Add Enum/Literal types for gender, mode, category | 15 min | Type safety |
| 15 | Add aria-labels to map, search, and risk indicators | 30 min | Accessibility |
| 16 | Switch to `datetime.now(timezone.utc)` | 5 min | Future-proof |
| 17 | Add keyboard arrow navigation to autocomplete | 45 min | UX improvement |
| 18 | Add loading skeletons to all panels | 30 min | Perceived performance |
| 19 | Use `asyncio.to_thread()` for ML prediction | 10 min | Unblock event loop |
| 20 | Add SW cache TTL for API responses | 30 min | Prevent stale data |

### P3: Low Priority (Nice to have)

| # | Fix | Effort | Impact |
|---|-----|--------|--------|
| 21 | Add backend unit tests | 3 hr | Quality assurance |
| 22 | Add frontend component tests | 2 hr | Quality assurance |
| 23 | Implement proper LRU cache with OrderedDict | 30 min | Performance |
| 24 | Add cache hit rate monitoring | 1 hr | Observability |
| 25 | Replace VITE_ prefix on backend env vars | 10 min | Convention correctness |

---

## 13. Potential New Features & Enhancements

### 13.1 Features to Improve Existing Functionality

| # | Enhancement | Effort | Description |
|---|-------------|--------|-------------|
| E1 | **Voice-activated safety check** | Medium | Use speech recognition + ElevenLabs TTS to allow hands-free safety queries while walking |
| E2 | **Real-time safety alerts** | Medium | WebSocket push notifications when new incidents reported near user's location |
| E3 | **Crowd-sourced safety ratings** | Medium | Let authenticated users rate locations (like Google reviews for safety), aggregate into score |
| E4 | **Multi-language support** | Medium | i18n for the UI + Gemini-translated safety tips |
| E5 | **Offline mode enhancement** | Medium | Pre-cache crime data for user's frequently visited areas for offline safety checks |
| E6 | **Comparative analysis** | Low | Side-by-side comparison of two locations' safety profiles |
| E7 | **Time-lapse safety visualization** | Medium | Animate the heatmap across 24 hours to show temporal safety patterns |
| E8 | **Safety corridors** | Medium | Suggest safest walking routes between A and B (not just analyze a single route) |
| E9 | **Neighborhood boundaries** | Low | Overlay neighborhood boundaries with per-neighborhood safety scores |
| E10 | **Predictive crime forecasting** | High | Time-series model predicting crime trends 30/90/365 days out |

### 13.2 Brand New Feature Ideas

| # | Feature | Effort | Description |
|---|---------|--------|-------------|
| N1 | **Safety Score API** (public) | Medium | RESTful API for developers to embed Lumos safety scores in their apps |
| N2 | **Travel itinerary safety planner** | High | Multi-stop trip planner with safety scores per stop and optimal timing |
| N3 | **Campus safety mode** | Medium | Specialized mode for college campuses with Clery Act data, blue light phone locations, campus police routes |
| N4 | **Group walk coordination** | Medium | Share a walk session with friends — everyone sees each other on the map in real-time |
| N5 | **Safety-aware business finder** | Medium | "Find the safest coffee shop near me" — combine POI data with safety scores |
| N6 | **Incident heatmap replay** | High | Scrub through historical incident data to see how crime patterns evolve over months/years |
| N7 | **Emergency SOS mode** | Medium | Panic button that shares location with emergency contacts and calls 911 |
| N8 | **Safety weather forecast** | Medium | "Safety forecast" showing predicted safety levels for the next 7 days based on events, weather, etc. |
| N9 | **AR overlay** | High | Camera view with safety zones overlay using device camera + GPS |
| N10 | **Insurance integration** | Low | Show how neighborhood safety scores correlate with insurance premiums |

### 13.3 Performance & Scalability Enhancements

| # | Enhancement | Effort | Description |
|---|-------------|--------|-------------|
| S1 | **Redis caching layer** | Medium | Replace in-memory TTL cache with Redis for persistence and multi-worker support |
| S2 | **PostgreSQL for persistence** | Medium | Store user reports, saved analyses, and ML training data |
| S3 | **Background job queue** | Medium | Offload heavy ML training and data collection to Celery/RQ workers |
| S4 | **CDN for static datasets** | Low | Serve pre-computed JSON datasets from CDN instead of reading from disk |
| S5 | **API response streaming** | Medium | Stream partial results as they arrive (heatmap while waiting for AI tips) |
| S6 | **WebSocket for real-time updates** | High | Live safety score updates, incident feeds, walk tracking coordination |

---

## 14. Hackathon Prize Strategy

### 🏆 Most Unique Application of Sphinx — $400 + Backpack

**What Sphinx offers:** Data tools and datasets for analytics.

**Strategy:** Integrate Sphinx's data APIs as an additional crime/safety data source in the multi-source aggregation pipeline. The "unique application" angle is that Lumos doesn't just visualize Sphinx data — it blends it with 12+ other sources into a single safety intelligence score through ML and formula-based aggregation.

**Implementation:**
- Add a `fetch_sphinx_data()` function in `data_fetchers.py`
- Blend Sphinx data into the scoring formula as an additional signal
- Show "Sphinx" as a data source in the dashboard attribution
- Highlight how Sphinx data fills gaps that other sources miss

**Effort:** 2-4 hours depending on Sphinx API complexity

---

### 🏆 [MLH] Best Use of ElevenLabs — Wireless Earbuds

**What ElevenLabs offers:** AI text-to-speech with natural, expressive voices.

**Strategy:** Add a **"Speak Safety Briefing"** feature that converts the safety analysis into an audio briefing using ElevenLabs' TTS API. This is a natural fit — travelers can listen to their safety briefing while walking (hands-free) rather than reading the dashboard.

**Implementation ideas:**
1. **Audio Safety Briefing:** Generate a spoken summary of the safety score, top risks, and tips
2. **Walk With Me Voice Companion:** During Walk With Me mode, provide real-time spoken alerts ("You're approaching a higher-risk area. Stay on well-lit streets.")
3. **Audio Safety Tips:** Convert Gemini AI safety tips to spoken audio
4. **Arrival announcements:** "You've arrived at your destination safely. Your walk took 12 minutes."

**Technical integration:**
```typescript
// Frontend: Add to AISafetyTips.tsx or create AudioBriefing.tsx
const speakBriefing = async (text: string) => {
  const response = await fetch('https://api.elevenlabs.io/v1/text-to-speech/{voice_id}', {
    method: 'POST',
    headers: { 'xi-api-key': ELEVENLABS_KEY, 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, model_id: 'eleven_turbo_v2' })
  });
  const audioBlob = await response.blob();
  const audio = new Audio(URL.createObjectURL(audioBlob));
  audio.play();
};
```

**Effort:** 3-5 hours

---

### 🏆 [MLH] Best Use of Gemini API — Google Swag Kits

**What to do:** Already using Gemini 2.5 Flash for AI safety tips and score refinement.

**Strategy:** **Deepen** the Gemini integration to make it the centerpiece:

**Enhancements to show off:**
1. **Already done:** AI safety tips generation, score refinement (±15), heatmap enrichment
2. **Add: Conversational safety assistant** — Chat interface where users ask "Is it safe to walk through downtown Atlanta at 2am?" and Gemini generates answers using the full safety data context
3. **Add: Gemini-powered route recommendation** — "What's the safest route from A to B?" using Gemini to reason about multiple routes
4. **Add: Incident summarization** — Gemini summarizes recent crime trends in natural language
5. **Add: Multi-modal analysis** — Allow users to upload a photo of a location and have Gemini assess visible safety factors (lighting, crowd density, etc.) via Gemini's vision capabilities

**Implementation:**
```python
# Backend: Add to routes.py
@app.post("/api/chat")
async def safety_chat(request: ChatRequest):
    context = f"Location: {request.location}, Safety Score: {request.score}/100, ..."
    model = genai.GenerativeModel("gemini-2.5-flash-preview-05-20")
    response = model.generate_content([context, request.question])
    return {"response": response.text}
```

**Effort:** 4-6 hours (conversational agent + vision)

---

### 🏆 [MLH] Best Use of Solana — Ledger Nano S Plus

**Strategy:** Add a **decentralized safety reputation system** on Solana:

**Implementation ideas:**
1. **Safety Report NFTs:** When users submit community safety reports, mint a lightweight NFT on Solana as an immutable incident record. Creates a tamper-proof community safety database.
2. **Safety Token Rewards:** Reward users with Lumos safety tokens (SPL token) for submitting verified safety reports. Tokens can be used for premium features.
3. **Decentralized Safety Scores:** Store safety scores on-chain for transparency and auditability. Anyone can verify that scores haven't been manipulated.
4. **Community Governance:** Token holders vote on which data sources to trust, creating a DAO for safety intelligence.

**Technical approach:**
- Use Solana's Web3.js SDK on the frontend
- Deploy a simple Solana program (smart contract) for report minting
- SPL token for rewards
- Near-zero transaction cost makes it viable for frequent reports

**Effort:** 6-10 hours (significant but high prize value)

---

### 🏆 [MLH] Best Use of Presage — Fitbit Inspire + Perks

**What Presage offers:** Real-time vital signs, movement, emotion, and focus tracking via standard camera.

**Strategy:** Integrate Presage into the **Walk With Me** feature for **biometric-aware safety:**

**Implementation ideas:**
1. **Stress-aware walking:** Monitor user's stress level via Presage during Walk With Me. If stress spikes (elevated heart rate, changed facial expression), automatically:
   - Trigger emergency contact notification
   - Show nearby police stations
   - Start recording
2. **Focus tracking for drivers:** Monitor driver alertness on route analysis for driving mode
3. **Emotional state-based recommendations:** If Presage detects anxiety, proactively show calming safety tips and highlight that the area is statistically safe
4. **Contactless check-in:** Use vital signs as a "proof of wellness" check-in during walks — if vitals suddenly stop being detected, alert emergency contacts

**Technical integration:**
- Presage SDK (JavaScript/Web SDK or native) in WalkWithMe.tsx
- Send vital sign data to backend for real-time risk adjustment
- Add `biometric_stress_level` as a factor in the scoring formula

**Effort:** 5-8 hours

---

### 🏆 [MLH] Best Use of Vultr — Portable Screens

**Strategy:** Deploy the entire Lumos stack on Vultr cloud infrastructure:

**Implementation ideas:**
1. **Cloud deployment:** Deploy FastAPI backend + React frontend on Vultr Compute
2. **GPU inference:** Use Vultr Cloud GPU for ML model training and real-time inference
3. **Scalability demo:** Show auto-scaling with multiple workers behind a load balancer
4. **Performance comparison:** Benchmark response times on Vultr vs. local — demonstrate cloud-powered sub-second safety analysis

**Effort:** 3-5 hours (spin up instances, containerize with Docker, deploy)

---

### 🏆 [MLH] Best Use of Snowflake API — M5Stack Tab5

**Strategy:** Use Snowflake as the **centralized crime data warehouse** with AI-powered querying:

**Implementation ideas:**
1. **Crime data warehouse:** Load all FBI UCR, NIBRS, and Socrata data into Snowflake tables
2. **Snowflake Cortex AI:** Use Snowflake's built-in LLM capabilities for natural language crime data queries ("What was the murder rate trend in Atlanta from 2018-2024?")
3. **RAG-powered safety chatbot:** Build a retrieval-augmented generation chatbot that queries the Snowflake crime database
4. **Real-time analytics:** Use Snowflake SQL for complex crime analytics (e.g., correlation between weather and crime, time-series forecasting)
5. Replace the flat-file JSON datasets with proper Snowflake tables for faster queries

**Effort:** 5-8 hours

---

### 🏆 GrowthFactor Challenge — $1,000 / $600 / $300

**Strategy:** Lumos directly serves GrowthFactor's retail and real estate customers:

**Implementation ideas:**
1. **Real estate safety overlay:** Show safety scores on a map for home buyers (scored by neighborhood/block)
2. **Retail location intelligence:** "Is this a safe location to open a store?" with foot traffic safety analysis
3. **Most Creative Data Source ($300):** Integrate unique data like:
   - Street lighting density (OpenStreetMap)
   - Yelp/Google business density as safety proxy
   - Social media sentiment analysis for neighborhood safety
   - Transit stop proximity data
   - 311 complaint data (broken windows theory indicator)

**Effort:** 4-6 hours

---

### 🏆 Best AI for Human Safety by SafetyKit — Arc'teryx Jacket

**Strategy:** Lumos IS an AI for human safety. This is the most natural fit.

**Emphasis points:**
1. **Multi-source AI aggregation** — 12+ data sources blended by ML + Gemini AI
2. **Real-time safety** — Live incident tracking, Walk With Me companion
3. **Proactive safety** — AI tips before you go, not after incidents happen
4. **Community safety** — Crowd-sourced reports complementing official data
5. If SafetyKit has an SDK/API: integrate it as another data source

**Effort:** 1-2 hours (mainly pitch preparation, possibly integrating SafetyKit API)

---

### 🏆 Best Use of Actian VectorAI DB — $500/$300/$200

**Strategy:** Use Actian VectorAI DB for **semantic crime search** and **embedding-based location similarity:**

**Implementation ideas:**
1. **Crime description embeddings:** Embed all crime incident descriptions into vector space. When a user queries a location, find semantically similar past incidents via vector similarity search.
2. **Location safety embeddings:** Embed each location's 15-feature safety profile as a vector. Find "locations similar to X" for comparative analysis.
3. **Natural language crime search:** "Show me areas with high car theft" → embed query → vector search against crime descriptions → show matching locations on map.
4. **Anomaly detection:** Use vector distance to detect locations with unusual crime patterns vs. their demographic peers.

**Effort:** 4-6 hours

---

### Priority Ranking for Prize Targeting

Based on **effort vs. reward** and **natural fit** with Lumos:

| Priority | Prize | Natural Fit | Effort | Prize Value |
|----------|-------|-------------|--------|-------------|
| 1 | **Best AI for Human Safety** (SafetyKit) | ⭐⭐⭐⭐⭐ Perfect | Low | Arc'teryx Jacket |
| 2 | **Best Use of Gemini API** | ⭐⭐⭐⭐⭐ Already using | Medium | Google Swag |
| 3 | **Best Use of ElevenLabs** | ⭐⭐⭐⭐ Great fit | Medium | Wireless Earbuds |
| 4 | **GrowthFactor Challenge** | ⭐⭐⭐⭐ Good fit | Medium | $1,000+ cash |
| 5 | **Best Use of Presage** | ⭐⭐⭐⭐ Strong fit | Medium-High | Fitbit + Perks |
| 6 | **Most Unique Sphinx** | ⭐⭐⭐ Good if data fits | Medium | $400 + Backpack |
| 7 | **Best Use of Vultr** | ⭐⭐⭐ Standard deploy | Low-Medium | Portable Screens |
| 8 | **Best Use of Snowflake** | ⭐⭐⭐ Good data fit | Medium-High | M5Stack Tab5 |
| 9 | **Best Use of Actian VectorAI** | ⭐⭐⭐ Creative angle | Medium-High | $500 cash |
| 10 | **Best Use of Solana** | ⭐⭐ Stretch | High | Ledger Nano S+ |

---

## 15. Technical Debt Summary

### Debt Categories

| Category | Items | Severity |
|----------|-------|----------|
| **No tests** | 0 backend tests, 0 frontend tests (only setup harness) | High |
| **No persistence** | In-memory reports, caches, rate limits | High |
| **Dead code** | Unused imports, unused deps, empty suggestions, broken API endpoints | Medium |
| **Code duplication** | Duplicate util functions, repeated fuzzy matching logic | Medium |
| **Type safety gaps** | Free-form strings for enums, `any` casts, missing validation | Medium |
| **Deprecated APIs** | `datetime.utcnow()`, `get_event_loop()`, `on_event("startup")` | Low |
| **Resource leaks** | httpx client, Mapbox popups, event listeners | Medium |
| **Accessibility** | No keyboard nav, color-only indicators, missing ARIA | Medium |
| **Scalability** | Single-process, no DB, no message queue | High |
| **ML model** | Circular training, adds ~0 value, heavy dependency | High |

### Estimated Cleanup Effort

| Priority | Tasks | Time |
|----------|-------|------|
| P0 Critical | Input validation, geocode consolidation, Firebase try/catch, synthetic labeling, httpx close | 1 hour |
| P1 High | Component decomposition, dependency pinning, Firestore reports, AbortController, React.memo, cleanup unused | 5 hours |
| P2 Medium | Accessibility, deprecated APIs, type safety, cache improvements | 4 hours |
| P3 Low | Tests, monitoring, documentation, full refactor | 8+ hours |
| **Total** | | **~18 hours** |

---

## 16. Appendix: File-by-File Reference

### Backend Files

| File | Lines | Purpose | Key Functions |
|------|-------|---------|---------------|
| `main.py` | ~17 | Entry point | uvicorn startup |
| `routes.py` | ~1,014 | All endpoints | 11 HTTP endpoints, rate limiter, startup |
| `models.py` | ~113 | Pydantic schemas | 15 models for request/response |
| `config.py` | ~96 | Configuration | API keys, feature names, constants |
| `scoring.py` | ~842 | Safety scoring | score computation, heatmap gen, Gemini AI |
| `ml_model.py` | ~986 | ML pipeline | Keras NN training, prediction, lazy loader |
| `data_fetchers.py` | ~1,578 | External APIs | 12+ API integrations, async HTTP |
| `cache.py` | ~64 | TTL cache | 7 cache instances |
| `city_crime_loader.py` | ~283 | UCR data | City/college/county crime lookups |
| `collect_state_data.py` | ~306 | Data collection | State data collection script |
| `fbi_cde_loader.py` | ~283 | FBI CDE files | Pre-downloaded FBI data loader |
| `nationwide_data.py` | ~826 | Hardcoded baseline | 50 states + 40 cities 2022 data |
| `nibrs_data.py` | ~892 | NIBRS pipeline | GA incident data, BJS profiles |

### Frontend Files

| File | Lines | Purpose | Key Exports |
|------|-------|---------|-------------|
| `App.tsx` | ~30 | App shell | Provider hierarchy, routing |
| `main.tsx` | ~10 | Entry point | SW registration |
| `index.css` | ~328 | Global styles | Dark/light themes, glassmorphism |
| `pages/Index.tsx` | ~932 | Main page | Entire app UI + state management |
| `pages/NotFound.tsx` | ~20 | 404 page | — |
| `hooks/useAuth.tsx` | ~50 | Auth context | AuthProvider, useAuth() |
| `hooks/useTheme.ts` | ~25 | Theme detection | useTheme() |
| `lib/api.ts` | ~300 | API client | 9 API functions |
| `lib/config.ts` | ~15 | Env config | API_BASE_URL, tokens |
| `lib/firebase.ts` | ~25 | Firebase init | auth, db, googleProvider |
| `lib/gemini.ts` | ~100 | AI tips | generateSafetyTips() |
| `lib/heatmap.ts` | ~445 | Map layers | 14 map layer functions |
| `lib/savedReports.ts` | ~40 | Firestore CRUD | save/get/delete reports |
| `lib/utils.ts` | ~5 | Utilities | cn() |
| `types/safety.ts` | ~80 | Type definitions | All safety data types |
| `components/GlobeView.tsx` | ~200 | Mapbox globe | 3D globe, rotation, themes |
| `components/RouteSearchBar.tsx` | ~400 | Search bar | Autocomplete, mode toggle |
| `components/ParameterPanel.tsx` | ~150 | Travel params | People, gender, time, duration |
| `components/SafetyDashboard.tsx` | ~250 | Score display | Score, incidents, time, sources |
| `components/HourlyRiskChart.tsx` | ~80 | Risk chart | 24h area chart |
| `components/AISafetyTips.tsx` | ~100 | AI tips panel | Gemini-powered tips |
| `components/EmergencyResources.tsx` | ~80 | Emergency contacts | Phone number links |
| `components/NearbyPOIs.tsx` | ~80 | Safe places | POI list with distances |
| `components/HistoricalTrends.tsx` | ~120 | Trend charts | Multi-year line chart |
| `components/ReportIncident.tsx` | ~150 | Report form | Community incident submission |
| `components/RouteSafetyPanel.tsx` | ~150 | Route results | Segment breakdown, walk button |
| `components/WalkWithMe.tsx` | ~200 | Live tracking | Geolocation, timer, sharing |
| `components/HeatmapLegend.tsx` | ~60 | Map legend | Gradient legend |
| `components/ThemeToggle.tsx` | ~30 | Theme switch | Light/dark toggle |
| `components/UserMenu.tsx` | ~80 | Auth menu | Sign in/out, saved reports |
| `components/ShareReport.tsx` | ~50 | Share button | Web Share API |
| `components/ExportReport.tsx` | ~100 | Export button | .txt file download |
| `components/ErrorBoundary.tsx` | ~40 | Error handler | Fallback UI |
| `components/LumosLogo.tsx` | ~50 | Logo SVG | Animated shield logo |
| `components/ui/*` | ~49 files | shadcn/ui | Radix-based UI primitives |

---

*Generated for Hacklytics 2026 — February 21, 2026*
