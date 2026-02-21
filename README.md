# Lumos — Real-Time Safety Intelligence

Lumos is a web app that provides real-time safety scores, crime analytics, route risk analysis, and AI-powered safety tips for any location in the United States. Built for Hacklytics 2026.

---

## Tech Stack

| Layer | Tech |
|-------|------|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui, Mapbox GL |
| Backend | Python 3.11, FastAPI, XGBoost, NIBRS data pipeline |
| Auth | Firebase Authentication |
| APIs | FBI CDE, Socrata (30+ cities), Census, NWS, Google Maps/Places/Routes, Gemini AI |

---

## Prerequisites

- **Node.js** ≥ 18
- **Python** 3.11 (the backend venv uses 3.11 — other versions may work but aren't tested)
- **npm** (comes with Node)

---

## Quick Start

### 1. Clone & install frontend dependencies

```bash
git clone <repo-url>
cd lumos
npm install
```

### 2. Set up the `.env` file

Create a `.env` file in the project root (it's gitignored). You'll need these keys:

```dotenv
# Frontend (Vite)
VITE_MAPBOX_TOKEN=<your-mapbox-token>
VITE_GOOGLE_MAPS_API_KEY=<your-google-maps-api-key>
VITE_GEMINI_API_KEY=<your-gemini-api-key>
VITE_API_BASE_URL=http://localhost:8000

# Firebase (frontend)
VITE_FIREBASE_API_KEY=<your-firebase-api-key>
VITE_FIREBASE_AUTH_DOMAIN=<project>.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=<project>
VITE_FIREBASE_STORAGE_BUCKET=<project>.firebasestorage.app
VITE_FIREBASE_MESSAGING_SENDER_ID=<sender-id>
VITE_FIREBASE_APP_ID=<app-id>
VITE_FIREBASE_MEASUREMENT_ID=<measurement-id>

# Backend
DATA_GOV_API_KEY=<your-fbi-api-key>
GOOGLE_MAPS_API_KEY=<your-google-maps-api-key>
```

> Ask a team member for the actual values — never commit `.env` to git.

### 3. Set up the backend

```bash
cd backend
python3.11 -m venv venv          # create virtual environment (use Python 3.11)
source venv/bin/activate         # activate it
pip install -r requirements.txt  # install dependencies
```

### 4. Get the NIBRS datasets

The backend loads Georgia NIBRS CSV data from `datasets/GA-2018` through `datasets/GA-2024`. These are gitignored due to size (~500 MB total).

Download them from the [FBI Crime Data Explorer](https://cde.ucr.cjis.gov/LATEST/webapp/#/pages/downloads) — select **NIBRS**, state **Georgia**, for each year 2018–2024. Unzip each into `datasets/GA-<YEAR>/`.

The directory should look like:

```
datasets/
  GA-2018/
    agencies.csv
    NIBRS_incident.csv
    NIBRS_OFFENSE.csv
    NIBRS_OFFENSE_TYPE.csv
    ...
  GA-2019/
    ...
  GA-2022/
    ...
```

> The backend will still start without these — it just won't have agency-level crime rates for Georgia.

### 5. Run everything

Open **two terminals**:

**Terminal 1 — Backend** (FastAPI on port 8000):

```bash
cd backend
source venv/bin/activate
python main.py
```

Wait until you see `Uvicorn running on http://0.0.0.0:8000` — NIBRS loading takes ~60–90 seconds on first start.

**Terminal 2 — Frontend** (Vite dev server on port 8080):

```bash
npm run dev
```

Open **http://localhost:8080** in your browser.

---

## Project Structure

```
lumos/
├── .env                    # API keys (gitignored)
├── package.json            # Frontend dependencies & scripts
├── vite.config.ts          # Vite config (port 8080)
├── tailwind.config.ts      # Tailwind CSS config
│
├── src/                    # Frontend (React + TypeScript)
│   ├── App.tsx             # Root component & routing
│   ├── main.tsx            # Entry point
│   ├── pages/              # Page components
│   ├── components/         # UI components
│   │   ├── SafetyDashboard.tsx
│   │   ├── ParameterPanel.tsx
│   │   ├── HourlyRiskChart.tsx
│   │   ├── RouteSafetyPanel.tsx
│   │   ├── AISafetyTips.tsx
│   │   ├── NearbyPOIs.tsx
│   │   └── ...
│   ├── hooks/              # Custom React hooks
│   ├── lib/                # Utilities
│   └── types/              # TypeScript types
│
├── backend/                # Backend (Python FastAPI)
│   ├── main.py             # Entry point (uvicorn on port 8000)
│   ├── routes.py           # API endpoints (/api/safety, /api/route, etc.)
│   ├── scoring.py          # Safety score computation & formulas
│   ├── data_fetchers.py    # External API calls (FBI, Socrata, Census, NWS, Google)
│   ├── nibrs_data.py       # NIBRS CSV data pipeline (GA agency-level stats)
│   ├── nationwide_data.py  # Nationwide city crime data
│   ├── fbi_cde_loader.py   # FBI Crime Data Explorer local cache loader
│   ├── ml_model.py         # XGBoost model loading & prediction
│   ├── config.py           # Config & constants
│   ├── models.py           # Pydantic request/response models
│   ├── cache.py            # In-memory TTL cache
│   ├── collect_state_data.py  # Training data collection
│   ├── train_model.py      # Model training script
│   ├── download_fbi_data.py   # FBI data downloader
│   ├── safety_model.xgb    # Trained XGBoost model
│   └── requirements.txt    # Python dependencies
│
├── datasets/               # Crime data (gitignored)
│   ├── GA-2018/ … GA-2024/ # NIBRS CSVs per year
│   ├── fbi_cde/            # Cached FBI CDE API responses
│   └── api_cache/          # Training data cache
│
└── public/                 # Static assets
```

---

## API Endpoints

All endpoints are under `http://localhost:8000`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/safety` | Get safety score for a location |
| POST | `/api/route` | Get route safety analysis between two points |
| GET | `/api/historical?state=GA` | Get historical crime trends for a state |
| POST | `/api/report` | Submit a user incident report |
| POST | `/api/ai-safety-tips` | Get AI-generated safety tips (Gemini) |

### Example: Safety Score Request

```bash
curl -X POST http://localhost:8000/api/safety \
  -H "Content-Type: application/json" \
  -d '{
    "lat": 34.0754,
    "lng": -84.2941,
    "timeOfTravel": "14:00",
    "duration": 60,
    "peopleCount": 1,
    "gender": "male"
  }'
```

---

## How the Safety Score Works

1. **Crime rate** — Uses the best available data source:
   - **GA cities**: NIBRS agency-level Part I crime rate (454 agencies, real per-city data)
   - **30+ major US cities**: Socrata open data portals (incident-level)
   - **All other US locations**: FBI state-level rate × urban/suburban/rural multiplier

2. **XGBoost model** — Trained on 8 features: crime rate, time of day, group size, gender, weather severity, population density, and incident diversity.

3. **Blended score** — 50% formula-based + 50% XGBoost prediction, scaled to 5–95.

4. **Risk level** — ≥70 = safe, 40–69 = caution, <40 = danger.

---

## Common Issues

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError` in backend | Make sure you activated the venv: `source venv/bin/activate` |
| Port 8000 already in use | `lsof -ti:8000 \| xargs kill -9` |
| Port 8080 already in use | `lsof -ti:8080 \| xargs kill -9` |
| Backend starts but NIBRS shows 0 incidents | Check that `datasets/GA-*/` directories have CSV files |
| Map not loading | Check `VITE_MAPBOX_TOKEN` is set in `.env` |
| "XGBoost model will load on first prediction" | Normal — model lazy-loads on first API call |
| Frontend can't reach backend | Verify `VITE_API_BASE_URL=http://localhost:8000` in `.env` |

---

## Scripts

```bash
# Frontend
npm run dev          # Start dev server (port 8080)
npm run build        # Production build
npm run lint         # Run ESLint
npm run test         # Run tests

# Backend
python main.py                # Start API server (port 8000)
python train_model.py         # Retrain XGBoost model
python download_fbi_data.py   # Download/refresh FBI CDE data cache
```
