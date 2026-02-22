<p align="center">
  <img src="https://img.shields.io/badge/HACKLYTICS-2026-FF6B35?style=for-the-badge&labelColor=1a1a2e&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0iI0ZGRDcwMCI+PHBhdGggZD0iTTEyIDJMMiA3bDEwIDUgMTAtNS0xMC01ek0yIDE3bDEwIDUgMTAtNS0xMC01LTEwIDV6TTIgMTJsMTAgNSAxMC01LTEwLTUtMTAgNXoiLz48L3N2Zz4="/>
</p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://readme-typing-svg.demolab.com?font=Outfit&weight=800&size=60&duration=3000&pause=1000&color=FFD700&center=true&vCenter=true&multiline=true&repeat=true&width=900&height=80&lines=LUMOS.AI">
    <img src="https://readme-typing-svg.demolab.com?font=Outfit&weight=800&size=60&duration=3000&pause=1000&color=FFD700&center=true&vCenter=true&multiline=true&repeat=true&width=900&height=80&lines=LUMOS.AI" alt="Lumos.AI"/>
  </picture>
</p>

<p align="center">
  <img src="https://readme-typing-svg.demolab.com?font=JetBrains+Mono&weight=500&size=22&duration=4000&pause=2000&color=C0C0C0&center=true&vCenter=true&repeat=true&width=850&height=35&lines=%E2%9C%A8+Real-Time+Safety+Intelligence+%E2%80%94+Powered+by+AI+%E2%9C%A8;%F0%9F%9B%A1%EF%B8%8F+25-Feature+XGBoost+%C3%97+Gemini+2.5+Flash+%C3%97+12%2C000%2B+Agencies;%F0%9F%8C%8D+Every+Address+in+America.+One+Safety+Score.;%F0%9F%93%9E+AI+Emergency+Operator+%E2%80%94+Calls+911+When+You+Can%27t+Speak" alt="Typing SVG" />
</p>

<p align="center">
 <a href="https://lumos-safety.netlify.app">
  <img src="https://img.shields.io/badge/%F0%9F%8C%90_LIVE_DEMO-lumos--safety.netlify.app-FFD700?style=for-the-badge&labelColor=0d1117" alt="Live Demo"/>
</a>
  <a href="#-quick-start"><img src="https://img.shields.io/badge/⚡_GET_STARTED-5_Minutes-00D4AA?style=for-the-badge&labelColor=0d1117" alt="Quick Start"/></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/React_18-61DAFB?style=flat-square&logo=react&logoColor=black" alt="React"/>
  <img src="https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white" alt="TypeScript"/>
  <img src="https://img.shields.io/badge/Vite_5-646CFF?style=flat-square&logo=vite&logoColor=white" alt="Vite"/>
  <img src="https://img.shields.io/badge/Tailwind_CSS-06B6D4?style=flat-square&logo=tailwindcss&logoColor=white" alt="Tailwind"/>
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/XGBoost-FF6600?style=flat-square&logo=xgboost&logoColor=white" alt="XGBoost"/>
  <img src="https://img.shields.io/badge/Gemini_2.5_Flash-4285F4?style=flat-square&logo=google&logoColor=white" alt="Gemini"/>
  <img src="https://img.shields.io/badge/Firebase-FFCA28?style=flat-square&logo=firebase&logoColor=black" alt="Firebase"/>
  <img src="https://img.shields.io/badge/Mapbox_GL-000000?style=flat-square&logo=mapbox&logoColor=white" alt="Mapbox"/>
  <img src="https://img.shields.io/badge/Python_3.11-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python"/>
</p>

<br/>

---

<br/>

> **🏆 Built for Hacklytics 2026** — Georgia Tech's premier data science hackathon.
>
> Lumos doesn't just show you crime data. It understands your context — *who* you are, *when* you're traveling, *how* you're moving — and computes a **personalized safety score** using real crime intelligence from **12,000+ law enforcement agencies**, an **XGBoost model trained on 25 features**, and **Gemini 2.5 Flash** for context-aware reasoning. And if you're ever in danger, Lumos can **call 911 for you** using an AI voice operator.

<br/>

## 🧭 Table of Contents

<details open>
<summary><b>Click to expand</b></summary>

- [✨ What is Lumos?](#-what-is-lumos)
- [🎯 Key Features](#-key-features)
- [🏗️ System Architecture](#️-system-architecture)
- [🧠 How the Safety Score Works](#-how-the-safety-score-works)
- [📞 AI Emergency Operator](#-ai-emergency-operator)
- [🗂️ Data Pipeline](#️-data-pipeline)
- [🛠️ Tech Stack](#️-tech-stack)
- [🔌 API Integrations](#-api-integrations)
- [📡 Backend API Reference](#-backend-api-reference)
- [⚡ Quick Start](#-quick-start)
- [📁 Project Structure](#-project-structure)
- [🧪 Testing](#-testing)
- [🚀 Deployment](#-deployment)
- [🐛 Troubleshooting](#-troubleshooting)
- [👥 Team](#-team)

</details>

<br/>

---

<br/>

## ✨ What is Lumos?

<table>
<tr>
<td width="60%">

**Lumos** is a real-time safety intelligence platform that answers one question:

> ***"Is it safe here, right now, for me?"***

Unlike static crime maps that show outdated dots on a screen, Lumos synthesizes **15+ data sources** in parallel — FBI crime databases, live Citizen app incidents, weather data, event feeds, moon illumination, and more — into a single **personalized safety score (0–100)** using a hybrid ML pipeline.

Every score is contextualized by:
- ⏰ **Time of day** — BJS-derived temporal crime multipliers
- 👤 **Personal factors** — gender, group size, travel mode
- 🌦️ **Weather conditions** — real-time NWS severity
- 🌙 **Lunar phase** — moon illumination correlates with visibility
- 📡 **Live incidents** — real-time Citizen app feed with 5-factor decay scoring
- 🎭 **Local events** — Ticketmaster crowd density proxy

</td>
<td width="40%">

```
        ╔══════════════════════╗
        ║                      ║
        ║   🟢 SAFETY: 82     ║
        ║   ━━━━━━━━━━━━━━━━  ║
        ║   Atlanta, GA        ║
        ║   2:30 PM · Sunny    ║
        ║                      ║
        ║   ▓▓▓▓▓▓▓▓▓▓▓░░░░  ║
        ║   Violent    Property ║
        ║                      ║
        ║   📊 24-Hour Curve   ║
        ║   ┌──────────────┐   ║
        ║   │    ╱╲         │   ║
        ║   │   ╱  ╲  ╱╲   │   ║
        ║   │──╱────╲╱──╲──│   ║
        ║   │ ╱          ╲ │   ║
        ║   └──────────────┘   ║
        ║   6AM    12PM   11PM ║
        ║                      ║
        ║  🤖 AI: "Stick to   ║
        ║  well-lit streets    ║
        ║  near Peachtree..."  ║
        ║                      ║
        ╚══════════════════════╝
```

</td>
</tr>
</table>

<br/>

---

<br/>

## 🎯 Key Features

<table>
<tr>
<td align="center" width="33%">

### 🎯 Safety Scoring
**25-Feature XGBoost + Formula Hybrid**

ML prediction (60%) blended with a physics-inspired formula fallback (40%) as a guardrail. Features include NIBRS agency crime rates, temporal profiles, weather severity, officer density, moon illumination, and live event feeds.

</td>
<td align="center" width="33%">

### 🌍 3D Globe Visualization
**Cinematic Mapbox GL Experience**

Auto-rotating 3D globe with fog + starfield, cinematic `flyTo` animations, dual heatmap layers (crime density + live incidents), color-coded route polylines, and POI markers — all theme-aware.

</td>
<td align="center" width="33%">

### 📞 AI Emergency Operator
**"LUMOS AI, calling on behalf of..."**

VAPI-powered outbound calls with Gemini 2.5 Flash as the conversational AI, ElevenLabs voice synthesis, and Deepgram Nova-2 transcription. Relays GPS updates every 30 seconds.

</td>
</tr>
<tr>
<td align="center" width="33%">

### 🗺️ Route Safety Analysis
**Segment-by-Segment Risk Scoring**

Enter origin → destination. Google Routes API generates waypoints. Each segment scored independently. Color-coded visualization (green → yellow → red). Time advancement per segment. Overall minimum-aware safety score.

</td>
<td align="center" width="33%">

### 🚶 Walk With Me
**GPS Guardian Angel Mode**

Real-time walk tracking with Haversine distance-to-destination, elapsed time, auto-arrival detection (50m radius), Web Share API location sharing, and direct 911 button. Your digital walking buddy.

</td>
<td align="center" width="33%">

### 🤖 AI Safety Chat
**Context-Aware Gemini Assistant**

Floating chat widget powered by Gemini 2.5 Flash with full location context, 10-message conversation history, suggested questions, and typing indicator. Ask anything about safety.

</td>
</tr>
<tr>
<td align="center" width="33%">

### 📊 Hourly Risk Curve
**24-Hour Predictive Timeline**

Area chart showing predicted risk levels across all 24 hours using BJS temporal crime multipliers per offense type (robbery 3.07× at night, assault 1.69×). "Now" reference line. Dynamic risk-colored fill.

</td>
<td align="center" width="33%">

### 📈 Historical Trends
**Multi-Year FBI Crime Intelligence**

Line charts tracking violent and property crime rates over multiple years via FBI Crime Data Explorer API. Trend direction indicators show whether crime is rising or falling.

</td>
<td align="center" width="33%">

### 🔴 Live Incidents
**Real-Time Citizen Feed**

Proxied Citizen app trending incidents with severity badges (🔴 critical → 🟢 low), relative timestamps, and clickable map focus. Powers the Citizen Incident Adjustment (CIA) scoring.

</td>
</tr>
<tr>
<td align="center" width="33%">

### 🏥 Nearby POIs
**Safety-Critical Locations**

Police stations, hospitals, and fire stations within radius. Distance calculations. Click to focus on map. Powered by Google Places (New) API.

</td>
<td align="center" width="33%">

### 💡 AI Safety Tips
**Gemini-Generated Guidance**

4 structured tips with priority badges (🔴 critical → 🟢 general). Context-aware based on location, time, weather, and crime patterns. Static fallback for reliability.

</td>
<td align="center" width="33%">

### 📄 Reports & Sharing
**Save, Export, Share**

Firestore-backed report saving. `.txt` export with ASCII art header. URL-parameter shareable links. Web Share API / clipboard support. User incident reporting with 8 types and 3 severity levels.

</td>
</tr>
</table>

<br/>

---

<br/>

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND — React + Vite + TypeScript                   │
│                                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────────┐  │
│  │  Index.tsx    │  │  GlobeView   │  │  Dashboard   │  │  Emergency System       │  │
│  │  (SPA Root)  │  │  (Mapbox GL) │  │  (Results)   │  │  Call Modal + ActiveBar │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────────┬──────────────┘  │
│         │                 │                 │                      │                 │
│  ┌──────▼─────────────────▼─────────────────▼──────────────────────▼──────────────┐  │
│  │                          lib/api.ts — Unified API Layer                        │  │
│  └────────────────────────────────┬──────────────────────────────────────────────-┘  │
│                                   │                                                 │
│  ┌────────────────────────────────▼──────────────────────────────────────────────┐   │
│  │  Firebase Auth │ Firestore (reports, profiles) │ RTDB (live call state)       │   │
│  └──────────────────────────────────────────────────────────────────────────────-┘   │
└──────────────────────────────────────┬──────────────────────────────────────────────-┘
                                       │ HTTPS
┌──────────────────────────────────────▼──────────────────────────────────────────────-┐
│                          BACKEND — FastAPI + Python 3.11                             │
│                                                                                     │
│  ┌────────────┐    ┌──────────────┐    ┌────────────────────────────────────────┐    │
│  │  routes.py  │───▶│  scoring.py   │───▶│  ml_model.py (XGBoost .ubj regressor) │    │
│  │  (15 endpts)│    │  (CIA + blend)│    │  25 features × LRU-cached inference   │    │
│  └─────┬──────┘    └──────────────┘    └────────────────────────────────────────┘    │
│        │                                                                            │
│  ┌─────▼───────────────────────────────────────────────────────────────────────────┐ │
│  │                       data_fetchers.py — Parallel Async Pipeline               │ │
│  │                                                                                │ │
│  │  FBI CDE ─┐                          ┌─ NWS Weather                            │ │
│  │  Socrata ─┤  ┌──────────────────┐    ├─ Census Population                      │ │
│  │  NIBRS   ─┤  │  asyncio.gather  │    ├─ Google Places POIs                     │ │
│  │  UCR DB  ─┤──│  (all in parallel)│───├─ Ticketmaster Events                    │ │
│  │  Citizen ─┤  └──────────────────┘    ├─ Astronomy (Moon)                       │ │
│  │  Google  ─┘                          └─ Google Routes                          │ │
│  └────────────────────────────────────────────────────────────────────────────────-┘ │
│                                                                                     │
│  ┌────────────────────────────────────────────────────────────────────────────────┐  │
│  │                          DATASETS — Pre-Loaded at Startup                      │  │
│  │  agency_profiles.json (12K+ agencies) │ city_crime_lookup.json (8,986 cities)  │  │
│  │  state_temporal_profiles.json (50+DC) │ college_crime_lookup.json (676)        │  │
│  │  county_crime_lookup.json (2,364)     │ nationwide_data.py (50 states)         │  │
│  └────────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────-┘
                                       │
┌──────────────────────────────────────▼──────────────────────────────────────────────-┐
│                    FIREBASE CLOUD FUNCTIONS (2nd Gen)                                │
│                                                                                     │
│  startEmergencyCall ─── VAPI Outbound Call + RTDB Context Write                     │
│  vapiLlm ───────────── Custom LLM Endpoint (Gemini 2.5 Flash)                      │
│  emergencyCallMessage ─ RTDB Updates + VAPI "control:say" Injection                 │
│  emergencyCallEnd ───── VAPI Hangup + RTDB Cleanup                                  │
│  vapiWebhook ────────── VAPI Server Events (end-of-call-report)                     │
└─────────────────────────────────────────────────────────────────────────────────────-┘
```

<br/>

---

<br/>

## 🧠 How the Safety Score Works

The safety scoring pipeline is a **10-stage process** that runs in under 2 seconds:

```
Step 1                    Step 2                   Step 3
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│ 📍 Geocode   │────────▶│ ⚡ Parallel   │────────▶│ 📊 Crime Rate│
│ Address      │         │ Data Fetch   │         │ Resolution   │
│              │         │ (8 sources)  │         │ (3-tier)     │
└──────────────┘         └──────────────┘         └──────────────┘
                                                         │
     ┌───────────────────────────────────────────────────┘
     ▼
Step 4                    Step 5                   Step 6
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│ 🤖 XGBoost   │────────▶│ ⚖️ 60/40     │────────▶│ 🤖 Gemini    │
│ 25-Feature   │         │ Hybrid Blend │         │ Refinement   │
│ Inference    │         │              │         │ (optional)   │
└──────────────┘         └──────────────┘         └──────────────┘
                                                         │
     ┌───────────────────────────────────────────────────┘
     ▼
Step 7                    Step 8                   Step 9 & 10
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│ 🔴 CIA       │────────▶│ 📈 24-Hour   │────────▶│ 🗺️ Heatmap + │
│ Live Incident│         │ Risk Curve   │         │ Response     │
│ Penalty ≤25  │         │ Generation   │         │ Assembly     │
└──────────────┘         └──────────────┘         └──────────────┘
```

### 3-Tier Crime Rate Resolution

The system finds the **most granular** crime data available for any US location:

| Priority | Source | Coverage | Granularity |
|:---:|---|---|---|
| 🥇 | **NIBRS Agency Profiles** | 12,000+ agencies | Per-agency offense mix, weapon rates, stranger rates, severity scores, officer counts |
| 🥈 | **FBI UCR Datasets** | 8,986 cities + 676 colleges + 2,364 counties | Annual per-offense crime counts |
| 🥉 | **State Baseline** | 50 states + DC | State rate × urban/suburban/rural multiplier |

### XGBoost Feature Vector (25 dimensions)

```python
FEATURE_NAMES = [
    "agency_part1_rate",       # Total Part I crime rate per 100K
    "agency_violent_rate",     # Violent crime rate per 100K
    "agency_property_rate",    # Property crime rate per 100K
    "agency_weapon_rate",      # Weapon offense rate
    "agency_stranger_rate",    # Stranger-on-stranger rate
    "agency_severity_score",   # Weighted severity composite
    "state_crime_rate_norm",   # State-level baseline (normalized)
    "population_group",        # City population category (1-9)
    "hourly_risk_ratio",       # BJS temporal multiplier for current hour
    "dow_risk_ratio",          # Day-of-week crime ratio
    "monthly_risk_ratio",      # Monthly crime seasonality
    "time_sin",                # Circular time encoding (sin)
    "time_cos",                # Circular time encoding (cos)
    "is_weekend",              # Binary weekend flag
    "people_count_norm",       # Group size (log-normalized)
    "gender_factor",           # Gender-based victimization rate
    "weather_severity",        # NWS weather severity (0-1)
    "officer_density",         # Officers per 100K population
    "is_college",              # Campus area flag
    "is_urban",                # Urban/suburban/rural classification
    "poi_density",             # Nearby safety POI density
    "live_events_norm",        # Ticketmaster event count (normalized)
    "live_incidents_norm",     # Citizen incident count (normalized)
    "moon_illumination",       # Lunar phase (0-1)
    "spatial_density_score",   # Spatial crime density from Socrata
]
```

### Citizen Incident Adjustment (CIA)

Real-time scoring modifier using live Citizen app incidents:

```
CIA_penalty = Σ (distance_decay × recency_decay × severity × credibility × status)
                                                                    capped at 25 points

distance_decay  = Gaussian, half-weight at 0.3 miles
recency_decay   = Exponential, half-life ~2.8 hours
severity        = level + incidentScore + color mapping
credibility     = 911-sourced > community-reported
status          = confirmed ↑ | closed ↓
```

### BJS Temporal Crime Multipliers

Safety varies dramatically by hour. The system applies **Bureau of Justice Statistics** temporal amplification per offense type:

| Crime Type | Night (10PM–6AM) | Evening (6PM–10PM) | Day (6AM–6PM) |
|:---:|:---:|:---:|:---:|
| **Robbery** | 3.07× | 1.53× | 0.47× |
| **Assault** | 1.69× | 1.42× | 0.62× |
| **Burglary** | 1.35× | 1.15× | 0.74× |
| **Vehicle Theft** | 2.06× | 1.23× | 0.54× |

<br/>

---

<br/>

## 📞 AI Emergency Operator

<table>
<tr>
<td width="50%">

### The Problem
In a dangerous situation, you might not be able to speak. You might be hiding. Someone might be near you. Calling 911 could put you at greater risk.

### The Solution
Lumos's **AI Emergency Operator** calls on your behalf. It speaks to the 911 operator as "LUMOS AI" — delivering your name, age, location, incident type, severity, and medical conditions. Every **30 seconds**, it relays your updated GPS coordinates.

You can send **silent text messages** from your phone that the AI reads aloud to the operator in real-time.

### How It Works

```
User ──text──▶ Firebase RTDB ──▶ Cloud Function
                                      │
                                      ▼
                               VAPI Outbound Call
                                      │
                          ┌───────────┼───────────┐
                          ▼           ▼           ▼
                    ElevenLabs   Gemini 2.5   Deepgram
                    (Voice)      (Brain)      (Ears)
                          │           │           │
                          └───────────┼───────────┘
                                      ▼
                              911 Operator hears:
                              "This is LUMOS AI,
                               calling on behalf of
                               Jane Doe, age 24..."
```

</td>
<td width="50%">

### Call Lifecycle

**Phase 1 — Profile Collection**
```
┌─────────────────────────────┐
│  📋 Emergency Profile       │
│                             │
│  Name: _______________      │
│  Age:  _______________      │
│  Medical: ____________      │
│  Contact: ____________      │
│  Incident: [Robbery ▼]     │
│  Severity: [● High   ]     │
│                             │
│  [📞 Start AI Call]         │
└─────────────────────────────┘
```

**Phase 2 — 10s Countdown** *(cancel window)*

**Phase 3 — Active Call**
```
┌─────────────────────────────┐
│  🔴 LUMOS AI CALL ACTIVE    │
│  Duration: 02:34            │
│                             │
│  📍 GPS: 33.7490, -84.3880 │
│  📍 Updated 12s ago        │
│                             │
│  💬 Type message to relay:  │
│  ┌─────────────────────┐    │
│  │ He went north on    │    │
│  │ Peachtree Street    │    │
│  └─────────────────────┘    │
│  [Send to Operator]         │
│                             │
│  📝 Live Transcript:        │
│  "...dispatching unit to    │
│   your location now..."     │
│                             │
│  [End Call]                  │
└─────────────────────────────┘
```

</td>
</tr>
</table>

### Voice Stack

| Component | Technology | Role |
|:---------:|:----------:|------|
| 🧠 **Brain** | Gemini 2.5 Flash | Conversational AI that speaks to the 911 operator, processes context, adapts responses |
| 🗣️ **Voice** | ElevenLabs | Neural text-to-speech synthesis — natural, calm emergency voice |
| 👂 **Ears** | Deepgram Nova-2 | Real-time speech-to-text transcription of the operator's responses |
| 📞 **Caller** | VAPI | Outbound call orchestration — manages the phone call lifecycle |
| 🔄 **Relay** | Firebase RTDB | Real-time state sync between user's phone and the active call |

<br/>

---

<br/>

## 🗂️ Data Pipeline

```
                         ┌──────────────────────────────────────┐
                         │        RAW DATA SOURCES              │
                         │                                      │
                         │  FBI NIBRS ─── 12,000+ agencies      │
                         │  FBI UCR  ─── 8,986 cities           │
                         │              676 colleges            │
                         │              2,364 counties          │
                         │  FBI CDE  ─── State-level trends     │
                         │  Socrata  ─── 30+ city portals       │
                         │  Census   ─── Population data        │
                         │  NWS      ─── Weather conditions     │
                         │  Citizen  ─── Live incidents          │
                         │  Ticketmaster ─ Local events          │
                         │  Astronomy ─── Moon phase             │
                         │  Google Places ─ POIs                 │
                         │  Google Routes ─ Directions           │
                         │                                      │
                         └──────────────┬───────────────────────┘
                                        │
                                        ▼
                         ┌──────────────────────────────────────┐
                         │     PREPROCESSING & CACHING          │
                         │                                      │
                         │  city_crime_loader ── UCR lookup DB   │
                         │  fbi_cde_loader ──── API response     │
                         │  nibrs_data ──────── Agency profiles  │
                         │  nationwide_data ─── 50-state base    │
                         │  cache.py ───────── TTL in-memory     │
                         │                                      │
                         └──────────────┬───────────────────────┘
                                        │
                                        ▼
                         ┌──────────────────────────────────────┐
                         │     ML INFERENCE & SCORING           │
                         │                                      │
                         │  25-feature vector construction       │
                         │           │                          │
                         │     ┌─────┴─────┐                    │
                         │     ▼           ▼                    │
                         │  XGBoost    Formula                  │
                         │  (60%)      (40%)                    │
                         │     └─────┬─────┘                    │
                         │           ▼                          │
                         │     Blended Score                    │
                         │           │                          │
                         │     ┌─────┴─────┐                    │
                         │     ▼           ▼                    │
                         │  Gemini       CIA                    │
                         │  Refine     Penalty                  │
                         │     └─────┬─────┘                    │
                         │           ▼                          │
                         │     Final Score (5–95)               │
                         └──────────────────────────────────────┘
```

### Socrata Open Data Coverage (30+ Cities)

<details>
<summary><b>Expand full city list</b></summary>

| City | City | City | City |
|------|------|------|------|
| Chicago, IL | New York, NY | Los Angeles, CA | San Francisco, CA |
| Seattle, WA | Atlanta, GA | Philadelphia, PA | Boston, MA |
| Austin, TX | Denver, CO | Washington, DC | Nashville, TN |
| Dallas, TX | Houston, TX | Baltimore, MD | Detroit, MI |
| Minneapolis, MN | Sacramento, CA | Kansas City, MO | San Antonio, TX |
| Columbus, OH | Tucson, AZ | Louisville, KY | St. Louis, MO |
| Cincinnati, OH | Charlotte, NC | Pittsburgh, PA | Mesa, AZ |
| Raleigh, NC | Oakland, CA | *+ dynamic ODN discovery for unlisted cities* | |

</details>

<br/>

---

<br/>

## 🛠️ Tech Stack

<table>
<tr>
<th align="center">Layer</th>
<th align="center">Technology</th>
</tr>
<tr>
<td><b>⚛️ Frontend</b></td>
<td>React 18 · TypeScript · Vite 5 (SWC) · Tailwind CSS 3 · shadcn/ui (Radix primitives) · React Router 6 · Framer Motion 11</td>
</tr>
<tr>
<td><b>🗺️ Mapping</b></td>
<td>Mapbox GL JS 3.18 — globe projection, heatmap layers, circle layers, route polylines, cinematic flyTo</td>
</tr>
<tr>
<td><b>📊 Charting</b></td>
<td>Recharts 2.15 — area, line, and bar charts for risk curves and historical trends</td>
</tr>
<tr>
<td><b>🔐 Auth & DB</b></td>
<td>Firebase Auth (Google sign-in) · Firestore (reports, profiles) · Realtime Database (live call state)</td>
</tr>
<tr>
<td><b>☁️ Serverless</b></td>
<td>Firebase Cloud Functions (2nd gen) — <code>onCall</code> / <code>onRequest</code> for VAPI integration</td>
</tr>
<tr>
<td><b>🐍 Backend</b></td>
<td>Python 3.11 · FastAPI · uvicorn · httpx (async) · orjson</td>
</tr>
<tr>
<td><b>🤖 ML</b></td>
<td>XGBoost regressor (.ubj) — 25 features, sigmoid ground truth, LRU-cached inference</td>
</tr>
<tr>
<td><b>🧠 AI</b></td>
<td>Google Gemini 2.5 Flash — safety tips, chat, score refinement, heatmap enrichment, route recommendations, emergency operator</td>
</tr>
<tr>
<td><b>🗣️ Voice</b></td>
<td>VAPI (outbound calling) · ElevenLabs (TTS) · Deepgram Nova-2 (STT)</td>
</tr>
<tr>
<td><b>🚀 Deploy</b></td>
<td>Frontend: <a href="https://lumos-safety.netlify.app">lumos-safety.netlify.app</a> · Backend: uvicorn · Functions: Firebase Cloud Run</td>
</tr>
</table>

<br/>

---

<br/>

## 🔌 API Integrations

> **15+ external APIs** fetched in parallel via `asyncio.gather` for sub-2-second response times.

| # | API | Purpose | What We Get |
|:-:|:---:|---------|-------------|
| 1 | 🔍 **FBI CDE** | Crime Data Explorer | State-level crime stats, historical multi-year trends |
| 2 | 📋 **FBI UCR** | Uniform Crime Reports | 8,986 cities + 676 colleges + 2,364 counties |
| 3 | 📡 **Socrata** | Open Data Portals | Real-time incident data from 30+ cities |
| 4 | 🌧️ **NWS** | National Weather Service | Weather conditions and severity |
| 5 | ☁️ **OpenWeatherMap** | Weather Fallback | Secondary weather source |
| 6 | 👥 **Census** | Population Bureau | Per-capita normalization |
| 7 | 📍 **Google Geocoding** | Address Resolution | Address ↔ coordinates |
| 8 | 🏥 **Google Places** | Nearby POIs | Police, hospitals, fire stations |
| 9 | 🛣️ **Google Routes** | Directions | Waypoints, duration, polylines |
| 10 | 🔴 **Citizen** | Live Incidents | Real-time trending feed |
| 11 | 🎫 **Ticketmaster** | Local Events | Crowd density proxy |
| 12 | 🌙 **Astronomy API** | Moon Phase | Illumination (visibility) |
| 13 | 🤖 **Gemini 2.5 Flash** | AI Intelligence | Tips, chat, refinement, emergency LLM |
| 14 | 📞 **VAPI** | Voice Calls | Outbound emergency calls |
| 15 | 🗣️ **ElevenLabs** | Text-to-Speech | AI operator voice |
| 16 | 👂 **Deepgram** | Speech-to-Text | Nova-2 transcription |

<br/>

---

<br/>

## 📡 Backend API Reference

All endpoints served from FastAPI (default: `http://localhost:8000`).

**Rate Limit**: 30 requests / minute / IP &nbsp;·&nbsp; **CORS**: `lumos-ai.live`, `localhost:*`

| Method | Endpoint | Description |
|:------:|----------|-------------|
| `POST` | `/api/safety` | **Core** — Full safety analysis with parallel data fetch, XGBoost + CIA → SafetyResponse |
| `POST` | `/api/route` | Route analysis — Google Routes → waypoint sampling → per-segment scoring |
| `GET` | `/api/historical` | Multi-year FBI crime trends by state |
| `GET` | `/api/nearby-pois` | Safety POIs via Google Places |
| `GET` | `/api/citizen-hotspots` | Citizen trending incidents proxy |
| `POST` | `/api/ai-tips` | Gemini safety tips (4 structured, JSON) |
| `POST` | `/api/safety-chat` | Conversational Q&A (Gemini + location context) |
| `POST` | `/api/route-recommendation` | AI route recommendation |
| `GET` | `/api/incident-summary` | AI incident summary |
| `POST` | `/api/reports` | Submit incident report |
| `GET` | `/api/reports` | Get nearby reports |
| `GET` | `/api/geocode` | Geocoding proxy |
| `GET` | `/api/autocomplete` | Places autocomplete proxy |
| `POST` | `/api/emergency-call` | Direct emergency call trigger |
| `GET` | `/api/health` | Health check |

<details>
<summary><b>📝 Example: Safety Score Request</b></summary>

```bash
curl -X POST http://localhost:8000/api/safety \
  -H "Content-Type: application/json" \
  -d '{
    "lat": 33.7490,
    "lng": -84.3880,
    "timeOfTravel": "22:00",
    "duration": 60,
    "peopleCount": 1,
    "gender": "female",
    "travelMode": "walking"
  }'
```

**Response** (abridged):
```json
{
  "safetyScore": 42,
  "riskLevel": "caution",
  "location": "Atlanta, GA",
  "crimeRate": 5834.2,
  "hourlyRisk": [0.31, 0.28, 0.25, "...24 values"],
  "incidentTypes": {
    "Assault": 24.3,
    "Robbery": 18.7,
    "Theft": 31.2
  },
  "weather": { "condition": "Clear", "severity": 0.1 },
  "nearbyPOIs": ["..."],
  "aiTips": ["..."],
  "emergencyNumbers": { "police": "911" },
  "heatmapData": ["..."],
  "citizenIncidents": ["..."],
  "dataSources": ["FBI NIBRS", "Socrata ATL", "NWS", "Citizen"]
}
```

</details>

<br/>

---

<br/>

## ⚡ Quick Start

### Prerequisites

| Requirement | Version |
|:-----------:|:-------:|
| Node.js | ≥ 18 |
| Python | 3.11 |
| npm | ≥ 9 |

### 1️⃣ Clone & Install

```bash
git clone https://github.com/your-org/lumos.ai.git
cd lumos.ai
npm install
```

### 2️⃣ Environment Variables

Create a `.env` file in the project root:

```dotenv
# Frontend (Vite)
VITE_MAPBOX_TOKEN=<your-mapbox-token>
VITE_GOOGLE_MAPS_API_KEY=<your-google-maps-key>
VITE_GEMINI_API_KEY=<your-gemini-key>
VITE_API_BASE_URL=http://localhost:8000

# Firebase
VITE_FIREBASE_API_KEY=<key>
VITE_FIREBASE_AUTH_DOMAIN=<project>.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=<project>
VITE_FIREBASE_STORAGE_BUCKET=<project>.firebasestorage.app
VITE_FIREBASE_MESSAGING_SENDER_ID=<id>
VITE_FIREBASE_APP_ID=<id>
VITE_FIREBASE_MEASUREMENT_ID=<id>

# Backend
DATA_GOV_API_KEY=<fbi-key>
GOOGLE_MAPS_API_KEY=<key>
GEMINI_API_KEY=<key>
```

> Ask a team member for actual values — never commit `.env` to git.

### 3️⃣ Backend Setup

```bash
cd backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4️⃣ Launch

```bash
# Terminal 1 — Backend (port 8000)
cd backend && source venv/bin/activate && python main.py

# Terminal 2 — Frontend (port 8080)
npm run dev
```

🌐 Open **http://localhost:8080** and start exploring.

<br/>

---

<br/>

## 📁 Project Structure

```
lumos.ai/
│
├── 📄 .env                          # API keys (gitignored)
├── 📄 package.json                  # Frontend deps & scripts
├── 📄 vite.config.ts                # Vite (port 8080, SWC)
├── 📄 tailwind.config.ts            # Tailwind + custom theme
├── 📄 firebase.json                 # Firebase config
│
├── 🎨 src/                          # ── FRONTEND ──────────────
│   ├── App.tsx                      # Root + routing
│   ├── main.tsx                     # Entry point
│   │
│   ├── pages/
│   │   ├── Index.tsx                # Main SPA (1,660 lines)
│   │   └── NotFound.tsx             # 404
│   │
│   ├── components/
│   │   ├── SafetyDashboard.tsx      # Score gauge, risk badge, crime bars
│   │   ├── GlobeView.tsx            # 3D Mapbox GL globe + heatmaps
│   │   ├── SafetyChatWidget.tsx     # Floating Gemini chat
│   │   ├── RouteSafetyPanel.tsx     # Route segments + warnings
│   │   ├── RouteSearchBar.tsx       # Dual-mode search + autocomplete
│   │   ├── WalkWithMe.tsx           # GPS tracking + auto-arrival
│   │   ├── EmergencyCallModal.tsx   # AI call: profile → countdown → active
│   │   ├── ActiveCallBar.tsx        # Draggable call bar + transcript
│   │   ├── EmergencyProfileModal.tsx # Profile editor
│   │   ├── EmergencyResources.tsx   # Emergency numbers (911, 988)
│   │   ├── LiveIncidents.tsx        # Citizen feed
│   │   ├── HourlyRiskChart.tsx      # 24-hour risk curve
│   │   ├── HistoricalTrends.tsx     # FBI trend lines
│   │   ├── NearbyPOIs.tsx           # Police, hospitals, fire
│   │   ├── AISafetyTips.tsx         # 4 Gemini tips
│   │   ├── ParameterPanel.tsx       # Time/gender/group/mode
│   │   ├── HeatmapLegend.tsx        # Layer legend
│   │   ├── ReportIncident.tsx       # User reports
│   │   ├── ExportReport.tsx         # .txt export
│   │   ├── ShareReport.tsx          # Share via URL/clipboard
│   │   ├── UserMenu.tsx             # Auth + saved reports
│   │   └── ui/                      # 40+ shadcn/ui primitives
│   │
│   ├── hooks/                       # useAuth, useEmergencyProfile, useTheme
│   ├── lib/                         # api, firebase, gemini, heatmap, utils
│   └── types/                       # TypeScript interfaces
│
├── 🐍 backend/                      # ── BACKEND ──────────────
│   ├── main.py                      # FastAPI + uvicorn
│   ├── routes.py                    # 15 endpoints
│   ├── scoring.py                   # Score computation + CIA
│   ├── ml_model.py                  # XGBoost inference
│   ├── data_fetchers.py             # Parallel async (15+ APIs)
│   ├── models.py                    # Pydantic schemas
│   ├── config.py                    # Constants + features
│   ├── cache.py                     # TTL in-memory cache
│   ├── nibrs_data.py                # Agency profile loader
│   ├── city_crime_loader.py         # UCR lookup DB
│   ├── fbi_cde_loader.py            # FBI CDE cache
│   ├── nationwide_data.py           # 50-state baseline
│   ├── train_safety_model.py        # Training script
│   └── safety_model_xgb.ubj        # Trained model
│
├── 📊 datasets/                     # ── DATASETS ──────────────
│   ├── agency_profiles.json         # 12K+ agencies
│   ├── city_crime_lookup.json       # 8,986 cities
│   ├── college_crime_lookup.json    # 676 colleges
│   ├── county_crime_lookup.json     # 2,364 counties
│   ├── state_temporal_profiles.json # 50 + DC temporal data
│   └── training_metadata.json       # Model metadata
│
├── ☁️  functions/                    # ── CLOUD FUNCTIONS ──────
│   ├── index.js                     # VAPI + Gemini + RTDB
│   └── package.json
│
└── 🌐 public/                       # ── STATIC ─────────────
    ├── manifest.json                # PWA manifest
    └── sw.js                        # Service worker
```

<br/>

---

<br/>

## 🧪 Testing

```bash
npm run test          # Run all tests (Vitest)
npm run test:watch    # Watch mode
```

Tests use **Vitest** + **React Testing Library** + **jsdom**.

<br/>

---

<br/>

## 🚀 Deployment

| Component | Platform | URL |
|:---------:|:--------:|:---:|
| Frontend | Surge / Vite Build | [lumos-safety.netlify.app](https://lumos-safety.netlify.app) |
| Backend | uvicorn | Port 8000 |
| Functions | Firebase Cloud Run | Auto-deployed |

```bash
npm run build              # Build frontend
npm run firebase:deploy    # Deploy Cloud Functions
```

<br/>

---

<br/>

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError` | Activate venv: `source backend/venv/bin/activate` |
| Port 8000 in use | `lsof -ti:8000 \| xargs kill -9` |
| Port 8080 in use | `lsof -ti:8080 \| xargs kill -9` |
| Map not loading | Verify `VITE_MAPBOX_TOKEN` in `.env` |
| XGBoost lazy-load message | Normal — loads on first prediction |
| Frontend ↛ Backend | Check `VITE_API_BASE_URL=http://localhost:8000` |
| Firebase auth errors | Verify all `VITE_FIREBASE_*` keys |
| Gemini failures | Check `GEMINI_API_KEY` in `.env` |

<br/>

---

<br/>

## 📋 Scripts

```bash
# ── Frontend ────────────────────────────────
npm run dev              # Dev server (port 8080)
npm run build            # Production build
npm run build:dev        # Development build
npm run lint             # ESLint
npm run test             # Vitest
npm run test:watch       # Vitest watch mode
npm run preview          # Preview build
npm run firebase:deploy  # Deploy functions

# ── Backend ─────────────────────────────────
python main.py                   # API server (port 8000)
python train_safety_model.py     # Retrain XGBoost
python collect_state_data.py     # Collect training data
python precompute_nibrs.py       # Precompute agency profiles
```

<br/>

---

<br/>

## 👥 Team

Built with ☕ and sleepless nights at **Hacklytics 2026** — Georgia Tech.

<br/>

---

<br/>

<p align="center">
  <img src="https://img.shields.io/badge/BUILT_WITH-❤️_AT_HACKLYTICS_2026-FFD700?style=for-the-badge&labelColor=0d1117" alt="Built at Hacklytics"/>
</p>

<p align="center">
  <i>Because everyone deserves to feel safe. 🕯️</i>
</p>

<p align="center">
  <sub>Lumos — <b>light in the darkness.</b></sub>
</p>
