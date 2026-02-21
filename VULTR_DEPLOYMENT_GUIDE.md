# Lumos Backend — Vultr Deployment Guide

> **Audience:** You (the Lumos developer). This guide is specific to your codebase — every path, file, env var, and command maps directly to what's in your repo.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [What Gets Deployed](#2-what-gets-deployed)
3. [Vultr Server Provisioning](#3-vultr-server-provisioning)
4. [Initial Server Setup](#4-initial-server-setup)
5. [Transfer Files to the Server](#5-transfer-files-to-the-server)
6. [Install Python &amp; System Dependencies](#6-install-python--system-dependencies)
7. [Create a Virtual Environment &amp; Install Packages](#7-create-a-virtual-environment--install-packages)
8. [Configure Environment Variables](#8-configure-environment-variables)
9. [Verify the App Starts](#9-verify-the-app-starts)
10. [Set Up Gunicorn (Production ASGI Server)](#10-set-up-gunicorn-production-asgi-server)
11. [Create a systemd Service](#11-create-a-systemd-service)
12. [Set Up Nginx Reverse Proxy](#12-set-up-nginx-reverse-proxy)
13. [Enable HTTPS with Let&#39;s Encrypt](#13-enable-https-with-lets-encrypt)
14. [Update CORS Origins in routes.py](#14-update-cors-origins-in-routespy)
15. [Firewall Configuration](#15-firewall-configuration)
16. [Update Your Frontend to Point to the Backend](#16-update-your-frontend-to-point-to-the-backend)
17. [Post-Deploy Verification](#17-post-deploy-verification)
18. [Maintenance &amp; Operations](#18-maintenance--operations)
19. [Troubleshooting](#19-troubleshooting)

---

## 1. Architecture Overview

Your Lumos backend is a **FastAPI** application that:

| Component                 | Detail                                                                                                                                                                                   |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Entry point**     | `backend/main.py` → imports `app` from `routes.py`, runs Uvicorn on `0.0.0.0:8000`                                                                                              |
| **Web framework**   | FastAPI 3.0.0 (your internal version tag)                                                                                                                                                |
| **ML model**        | Pre-trained XGBoost model (`backend/safety_model_xgb.ubj`, ~7.7 MB), lazy-loaded on first prediction via `ml_model.py` → `_ModelProxy`                                            |
| **Data pipeline**   | On startup,`nibrs_data.py → initialize_nibrs()` loads pre-computed JSON profiles from `datasets/agency_profiles.json` (11 MB) and `datasets/state_temporal_profiles.json` (44 KB) |
| **Static datasets** | FBI CDE cached data (`datasets/fbi_cde/`, ~43 MB), city/college/county crime lookups (~2.7 MB combined), NIBRS raw data (`datasets/{STATE}-{YEAR}/`, ~48 GB total)                   |
| **External APIs**   | FBI CDE API, Google Maps/Places, Gemini AI, NWS Weather, Census, Socrata (city open data), Ticketmaster, Citizen, Astronomy API, OpenWeatherMap, Crimeometer                             |
| **Caching**         | In-memory TTL caches (`cache.py`) — FBI (24h), city (30m), weather (15m), census (7d), POIs (24h)                                                                                     |
| **Rate limiting**   | In-memory, 30 req/min/IP                                                                                                                                                                 |

### API Endpoints

| Method   | Path                      | Purpose                                                   |
| -------- | ------------------------- | --------------------------------------------------------- |
| `POST` | `/api/safety`           | Main safety score for a location (ML + Gemini refinement) |
| `POST` | `/api/route`            | Route-based safety analysis with per-segment scoring      |
| `GET`  | `/api/historical`       | Historical crime trends by state                          |
| `GET`  | `/api/nearby-pois`      | Nearby police stations, hospitals, fire stations          |
| `POST` | `/api/reports`          | Submit user safety reports                                |
| `GET`  | `/api/reports`          | Retrieve nearby user reports                              |
| `GET`  | `/api/health`           | Health check                                              |
| `GET`  | `/api/geocode`          | Google Maps geocoding proxy                               |
| `GET`  | `/api/autocomplete`     | Google Places autocomplete proxy                          |
| `GET`  | `/api/citizen-hotspots` | Citizen app incident proxy                                |
| `POST` | `/api/ai-tips`          | Gemini-powered safety tips                                |

---

## 2. What Gets Deployed

### Files you MUST deploy:

```
backend/
├── main.py                    # Entry point
├── routes.py                  # All API endpoints (1082 lines)
├── config.py                  # API keys, feature names, constants
├── models.py                  # Pydantic request/response schemas
├── data_fetchers.py           # External API integrations (1732 lines)
├── ml_model.py                # XGBoost model loader
├── scoring.py                 # Safety scoring logic (1285 lines)
├── cache.py                   # In-memory TTL cache
├── nibrs_data.py              # NIBRS data pipeline
├── city_crime_loader.py       # City/college/county crime lookups
├── fbi_cde_loader.py          # FBI CDE data reader
├── safety_model_xgb.ubj      # Pre-trained XGBoost model (7.7 MB)
├── requirements.txt           # Python dependencies
```

### Dataset files you MUST deploy:

```
datasets/
├── agency_profiles.json           # 11 MB — loaded at startup by nibrs_data.py
├── state_temporal_profiles.json   # 44 KB — loaded at startup by nibrs_data.py
├── city_crime_lookup.json         # 1.9 MB — loaded on first request by city_crime_loader.py
├── college_crime_lookup.json      # 256 KB — loaded on first request
├── county_crime_lookup.json       # 544 KB — loaded on first request
├── training_metadata.json         # 4 KB
├── fbi_cde/                       # ~43 MB — FBI CDE cached data (IMPORTANT: prevents live API calls)
│   ├── summarized/
│   ├── nibrs/
│   ├── arrest/
│   ├── hate_crime/
│   ├── shr/
│   ├── supplemental/
│   ├── pe/
│   └── lesdc/
```

### Files you do NOT need to deploy:

- `datasets/{STATE}-{YEAR}/` directories (~48 GB of raw NIBRS data) — these are **training data** used to generate `agency_profiles.json` and `state_temporal_profiles.json`. The pre-computed JSONs are all the server needs.
- `datasets/offensesByCity.xlsx`, `offensesByCollege.xlsx`, `offensesByCounty.xlsx` — source Excel files already converted to JSON lookups.
- `backend/train_safety_model.py` — training script (not needed in production).
- `backend/precompute_nibrs.py` — pre-computation script (not needed in production).
- `backend/collect_state_data.py` — data collection utilities.
- `backend/nationwide_data.py` — data collection utilities.
- `backend/test_alignment.py` — test file.
- `backend/nibrs_data.py.bak` — backup file.

---

## 3. Vultr Server Provisioning

### 3.1 Create an Account

1. Go to [https://www.vultr.com](https://www.vultr.com) and sign up.

### 3.2 Deploy a Cloud Compute Instance

1. Click **"Deploy +"** → **"Cloud Compute"**
2. Choose your configuration:

| Setting                | Recommended Value                                                                                                                                                                                   |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Type**         | Cloud Compute — Shared CPU (cheapest, sufficient for this app)                                                                                                                                     |
| **Location**     | Pick the region closest to your users (e.g., Atlanta, New York, Chicago)                                                                                                                            |
| **Image**        | **Ubuntu 22.04 LTS** (or 24.04 LTS)                                                                                                                                                           |
| **Plan**         | **2 vCPU / 4 GB RAM / 80 GB SSD** ($24/mo) — minimum for XGBoost model loading + simultaneous requests. If budget is tight, 1 vCPU / 2 GB RAM ($12/mo) works but may be slow on cold starts. |
| **Auto backups** | Optional (recommended, +20%)                                                                                                                                                                        |
| **SSH Key**      | Add your public SSH key (see below)                                                                                                                                                                 |
| **Hostname**     | `lumos-api`                                                                                                                                                                                       |

### 3.3 Add Your SSH Key (if you haven't already)

On your Mac, check if you have one:

```bash
cat ~/.ssh/id_ed25519.pub
# or
cat ~/.ssh/id_rsa.pub
```

If not, generate one:

```bash
ssh-keygen -t ed25519 -C "your@email.com"
cat ~/.ssh/id_ed25519.pub
```

Copy the output and paste it into the Vultr SSH key field during deployment.

### 3.4 Note Your Server IP

After deployment (~60 seconds), note the **IP address** from the Vultr dashboard. We'll call it `YOUR_SERVER_IP` throughout this guide.

---

## 4. Initial Server Setup

### 4.1 SSH into the Server

```bash
ssh root@YOUR_SERVER_IP
```

### 4.2 Create a Dedicated User

```bash
adduser lumos
usermod -aG sudo lumos

# Copy SSH keys to the new user
mkdir -p /home/lumos/.ssh
cp ~/.ssh/authorized_keys /home/lumos/.ssh/
chown -R lumos:lumos /home/lumos/.ssh
chmod 700 /home/lumos/.ssh
chmod 600 /home/lumos/.ssh/authorized_keys
```

### 4.3 Update the System

```bash
apt update && apt upgrade -y
apt install -y build-essential curl wget git unzip software-properties-common
```

### 4.4 Set the Timezone (optional but recommended for log readability)

```bash
timedatectl set-timezone America/New_York
```

Now log out and log back in as the `lumos` user:

```bash
exit
ssh lumos@YOUR_SERVER_IP
```

---

## 5. Transfer Files to the Server

### 5.1 Prepare a Deployment Bundle (on your Mac)

Since the full `datasets/` folder is 48 GB (mostly raw training data you don't need), create a lean deployment package:

```bash
cd /Users/heetshah/Documents/hacklytics2026/lumos

# Create a deployment staging directory
mkdir -p /tmp/lumos-deploy/backend
mkdir -p /tmp/lumos-deploy/datasets/fbi_cde

# Copy backend code + model
cp backend/main.py backend/routes.py backend/config.py backend/models.py \
   backend/data_fetchers.py backend/ml_model.py backend/scoring.py \
   backend/cache.py backend/nibrs_data.py backend/city_crime_loader.py \
   backend/fbi_cde_loader.py backend/requirements.txt \
   backend/safety_model_xgb.ubj \
   /tmp/lumos-deploy/backend/

# Copy required datasets (NOT the 48GB raw NIBRS data)
cp datasets/agency_profiles.json \
   datasets/state_temporal_profiles.json \
   datasets/city_crime_lookup.json \
   datasets/college_crime_lookup.json \
   datasets/county_crime_lookup.json \
   datasets/training_metadata.json \
   /tmp/lumos-deploy/datasets/

# Copy the FBI CDE cache directory
cp -r datasets/fbi_cde/ /tmp/lumos-deploy/datasets/fbi_cde/

# Copy the .env file (you'll edit it on the server)
cp .env /tmp/lumos-deploy/.env
```

### 5.2 Check Bundle Size

```bash
du -sh /tmp/lumos-deploy/
# Should be ~70-80 MB, NOT 48 GB
```

### 5.3 Transfer to Server via rsync

```bash
rsync -avz --progress /tmp/lumos-deploy/ lumos@YOUR_SERVER_IP:/home/lumos/lumos/
```

Or if you prefer tar + scp:

```bash
cd /tmp
tar -czf lumos-deploy.tar.gz lumos-deploy/
scp lumos-deploy.tar.gz lumos@YOUR_SERVER_IP:/home/lumos/

# Then on the server:
ssh lumos@YOUR_SERVER_IP
cd /home/lumos
tar -xzf lumos-deploy.tar.gz
mv lumos-deploy lumos
rm lumos-deploy.tar.gz
```

### 5.4 Verify Directory Structure on Server

```bash
ssh lumos@YOUR_SERVER_IP
ls -la /home/lumos/lumos/
# Should show: backend/  datasets/  .env

ls -la /home/lumos/lumos/backend/
# Should show all .py files + safety_model_xgb.ubj + requirements.txt

ls -la /home/lumos/lumos/datasets/
# Should show: agency_profiles.json, city_crime_lookup.json, etc. + fbi_cde/
```

---

## 6. Install Python & System Dependencies

SSH into the server as the `lumos` user and run:

```bash
# Add deadsnakes PPA for Python 3.12 (Ubuntu 22.04 ships 3.10)
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3.12-dev python3-pip

# Verify
python3.12 --version
# Should output: Python 3.12.x
```

> **Note:** Your local machine runs Python 3.14 (bleeding edge). Python 3.12 is the latest stable version widely supported by XGBoost, scikit-learn, and all your dependencies. Everything in your code is compatible with 3.12+.

Also install system libraries needed by numpy/scikit-learn:

```bash
sudo apt install -y libopenblas-dev liblapack-dev gfortran
```

---

## 7. Create a Virtual Environment & Install Packages

```bash
cd /home/lumos/lumos
python3.12 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel

# Install your dependencies
pip install -r backend/requirements.txt

# Install gunicorn (production ASGI server)
pip install gunicorn uvicorn[standard]
```

### Verify critical imports:

```bash
python -c "import fastapi; print('FastAPI:', fastapi.__version__)"
python -c "import xgboost; print('XGBoost:', xgboost.__version__)"
python -c "import sklearn; print('scikit-learn:', sklearn.__version__)"
python -c "import httpx; print('httpx:', httpx.__version__)"
python -c "import google.generativeai; print('Gemini SDK: OK')"
```

---

## 8. Configure Environment Variables

Edit the `.env` file on the server with your actual production API keys:

```bash
nano /home/lumos/lumos/.env
```

Your backend reads these variables from `config.py` (which loads `.env` from one directory above `backend/`):

```env
# ── Backend API Keys (REQUIRED for full functionality) ──

# Google Maps (geocoding, places, directions, reverse geocode)
GOOGLE_MAPS_API_KEY=your_production_google_maps_key

# Gemini AI (safety score refinement + AI tips + heatmap enrichment)
VITE_GEMINI_API_KEY=your_gemini_api_key

# FBI Crime Data Explorer (fallback when local cache misses)
DATA_GOV_API_KEY=your_data_gov_key

# Socrata Open Data (city-level crime feeds: Chicago, NYC, LA, etc.)
SOCRATA_APP_TOKEN=your_socrata_app_token
SOCRATA_SECRET_TOKEN=your_socrata_secret_token
SOCRATA_KEY_ID=your_socrata_key_id
SOCRATA_KEY_SECRET=your_socrata_key_secret

# Ticketmaster (live events near location)
TICKETMASTER_API_KEY=your_ticketmaster_key

# Crimeometer (live crime incident data)
CRIMEOMETER_API_KEY=your_crimeometer_key

# Astronomy API (moon illumination for safety scoring)
ASTRONOMY_APP_ID=your_astronomy_app_id
ASTRONOMY_APP_SECRET=your_astronomy_app_secret

# OpenWeatherMap (weather conditions + severity scoring)
OPENWEATHERMAP_API_KEY=your_openweathermap_key
```

> **IMPORTANT:** The `config.py` file loads `.env` from `Path(__file__).resolve().parent.parent / ".env"` — that means it expects `.env` to be at `/home/lumos/lumos/.env` (one level above `backend/`). This is already correct with the directory structure above.

### Secure the .env file

```bash
chmod 600 /home/lumos/lumos/.env
```

---

## 9. Verify the App Starts

```bash
cd /home/lumos/lumos/backend
source /home/lumos/lumos/venv/bin/activate
python main.py
```

You should see log output like:

```
INFO:     Loaded 5847 agency profiles
INFO:     Loaded 51 state profiles
INFO:     NIBRS data pipeline loaded: 5847 agencies, 51 states, covering 51 unique states
INFO:     XGBoost model will lazy-load on first prediction
INFO:     Started server process [12345]
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Test it (from another terminal on the server, or from your Mac):

```bash
# Health check
curl http://YOUR_SERVER_IP:8000/api/health
# Expected: {"status":"ok","model":"xgboost","version":"4.0.0"}

# Quick safety test
curl -X POST http://YOUR_SERVER_IP:8000/api/safety \
  -H "Content-Type: application/json" \
  -d '{"lat": 33.749, "lng": -84.388, "peopleCount": 1, "gender": "male", "timeOfTravel": "22:00"}'
```

Press `Ctrl+C` to stop the dev server once verified.

---

## 10. Set Up Gunicorn (Production ASGI Server)

Uvicorn alone is fine for development but not recommended for production. Use **Gunicorn with Uvicorn workers** for process management, auto-restart, and multi-worker support.

### 10.1 Create a Gunicorn Config File

```bash
cat > /home/lumos/lumos/gunicorn.conf.py << 'EOF'
# Gunicorn configuration for Lumos FastAPI backend
import multiprocessing

# Bind to localhost only (Nginx will proxy)
bind = "127.0.0.1:8000"

# Workers: for a 2-vCPU server, 2-3 workers is ideal
# Each worker loads the XGBoost model + NIBRS data (~200 MB RAM each)
workers = 2

# Use Uvicorn's ASGI worker class
worker_class = "uvicorn.workers.UvicornWorker"

# Timeout: some requests (Gemini AI, multiple API calls) can take 15-30s
timeout = 120
graceful_timeout = 30
keepalive = 5

# Logging
accesslog = "/home/lumos/lumos/logs/access.log"
errorlog = "/home/lumos/lumos/logs/error.log"
loglevel = "info"

# Preload app so model + NIBRS data are shared across workers (saves RAM)
preload_app = True

# Auto-restart workers after N requests (prevents memory leaks)
max_requests = 1000
max_requests_jitter = 50
EOF
```

### 10.2 Create the Logs Directory

```bash
mkdir -p /home/lumos/lumos/logs
```

### 10.3 Test Gunicorn

```bash
cd /home/lumos/lumos/backend
source /home/lumos/lumos/venv/bin/activate
gunicorn main:app -c /home/lumos/lumos/gunicorn.conf.py
```

Verify:

```bash
curl http://127.0.0.1:8000/api/health
```

Press `Ctrl+C` to stop.

---

## 11. Create a systemd Service

This ensures the backend starts automatically on boot and restarts on crash.

```bash
sudo nano /etc/systemd/system/lumos-api.service
```

Paste:

```ini
[Unit]
Description=Lumos Safety API (FastAPI + XGBoost)
After=network.target
Wants=network-online.target

[Service]
Type=notify
User=lumos
Group=lumos
WorkingDirectory=/home/lumos/lumos/backend
Environment="PATH=/home/lumos/lumos/venv/bin:/usr/bin:/bin"
ExecStart=/home/lumos/lumos/venv/bin/gunicorn main:app -c /home/lumos/lumos/gunicorn.conf.py
ExecReload=/bin/kill -s HUP $MAINPID
Restart=on-failure
RestartSec=5
StartLimitBurst=5
StartLimitIntervalSec=60
KillMode=mixed
TimeoutStopSec=30

# Security hardening
NoNewPrivileges=yes
PrivateTmp=yes
ProtectHome=read-only
ReadWritePaths=/home/lumos/lumos/logs

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable lumos-api
sudo systemctl start lumos-api

# Check status
sudo systemctl status lumos-api

# View live logs
sudo journalctl -u lumos-api -f
```

---

## 12. Set Up Nginx Reverse Proxy

### 12.1 Install Nginx

```bash
sudo apt install -y nginx
```

### 12.2 Create Nginx Config

```bash
sudo nano /etc/nginx/sites-available/lumos-api
```

Paste:

```nginx
server {
    listen 80;
    server_name YOUR_DOMAIN_OR_IP;
    # e.g., server_name api.lumos-safety.com;
    # or:   server_name YOUR_SERVER_IP;

    # Max request body size (safety requests are small, but future-proof)
    client_max_body_size 5M;

    # Gzip compression for JSON responses
    gzip on;
    gzip_types application/json;
    gzip_min_length 1000;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeout settings (Gemini + multi-API gather can be slow)
        proxy_connect_timeout 10s;
        proxy_read_timeout 120s;
        proxy_send_timeout 30s;

        # WebSocket support (not used currently, but won't hurt)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Block access to internal paths
    location ~ /\. {
        deny all;
    }
}
```

### 12.3 Enable the Site

```bash
sudo ln -s /etc/nginx/sites-available/lumos-api /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

### 12.4 Test

```bash
curl http://YOUR_SERVER_IP/api/health
# Should return: {"status":"ok","model":"xgboost","version":"4.0.0"}
```

---

## 13. Enable HTTPS with Let's Encrypt

> **Prerequisite:** You need a domain name (e.g., `api.lumos-safety.com`) pointed to your server's IP via an A record in your DNS provider. If you're just using the raw IP, skip this section.

### 13.1 Install Certbot

```bash
sudo apt install -y certbot python3-certbot-nginx
```

### 13.2 Obtain Certificate

```bash
sudo certbot --nginx -d api.yourdomain.com
```

Follow the prompts. Certbot will automatically modify your Nginx config to enable HTTPS and redirect HTTP → HTTPS.

### 13.3 Verify Auto-Renewal

```bash
sudo certbot renew --dry-run
```

Certbot installs a systemd timer that auto-renews certificates every 60 days.

---

## 14. Update CORS Origins in routes.py

Your `routes.py` currently only allows localhost origins. You **must** update this for production.

Edit `routes.py` on the server:

```bash
nano /home/lumos/lumos/backend/routes.py
```

Find the `_allowed_origins` block (around line 63) and add your frontend's production URL:

```python
_allowed_origins = [
    # Local development
    f"http://localhost:{p}" for p in range(3000, 3010)
] + [
    f"http://localhost:{p}" for p in range(5173, 5180)
] + [
    f"http://127.0.0.1:{p}" for p in range(3000, 3010)
] + [
    f"http://127.0.0.1:{p}" for p in range(5173, 5180)
] + [
    # ── Production origins (ADD YOUR FRONTEND URL HERE) ──
    "https://your-frontend-domain.com",
    "https://www.your-frontend-domain.com",
    # If deploying frontend to Vercel/Netlify:
    # "https://lumos-safety.vercel.app",
]
```

After editing, restart the service:

```bash
sudo systemctl restart lumos-api
```

---

## 15. Firewall Configuration

### 15.1 Configure UFW

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH
sudo ufw allow 22/tcp

# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Do NOT expose port 8000 directly (Nginx proxies it)
# sudo ufw allow 8000/tcp  ← DON'T do this

sudo ufw enable
sudo ufw status
```

### 15.2 Vultr Firewall (optional, extra layer)

In the Vultr dashboard:

1. Go to **Products** → **Firewall**
2. Create a new firewall group
3. Add rules: Allow TCP 22, 80, 443 from anywhere
4. Attach the firewall group to your instance

---

## 16. Update Your Frontend to Point to the Backend

In your frontend `.env` file (locally and in your frontend deployment), update:

```env
VITE_API_BASE_URL=https://api.yourdomain.com
# or if using raw IP without HTTPS:
# VITE_API_BASE_URL=http://YOUR_SERVER_IP
```

Rebuild and redeploy your frontend.

---

## 17. Post-Deploy Verification

Run these checks from your local machine:

```bash
# 1. Health check
curl https://api.yourdomain.com/api/health

# 2. Safety score
curl -X POST https://api.yourdomain.com/api/safety \
  -H "Content-Type: application/json" \
  -d '{"lat": 33.749, "lng": -84.388, "peopleCount": 1, "gender": "male", "timeOfTravel": "22:00"}'

# 3. Route analysis
curl -X POST https://api.yourdomain.com/api/route \
  -H "Content-Type: application/json" \
  -d '{"originLat": 33.749, "originLng": -84.388, "destLat": 33.789, "destLng": -84.384, "mode": "walking"}'

# 4. Historical data
curl "https://api.yourdomain.com/api/historical?state=GA"

# 5. Geocode
curl "https://api.yourdomain.com/api/geocode?query=Atlanta%2C%20GA"

# 6. AI Tips
curl -X POST https://api.yourdomain.com/api/ai-tips \
  -H "Content-Type: application/json" \
  -d '{"locationName": "Atlanta, GA", "safetyIndex": 65, "incidentTypes": ["theft", "assault"]}'
```

---

## 18. Maintenance & Operations

### 18.1 View Logs

```bash
# Application logs (via systemd journal)
sudo journalctl -u lumos-api -f

# Gunicorn access/error logs
tail -f /home/lumos/lumos/logs/access.log
tail -f /home/lumos/lumos/logs/error.log

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### 18.2 Restart the Service

```bash
sudo systemctl restart lumos-api
```

### 18.3 Deploy Code Updates

From your Mac:

```bash
# Copy updated backend files
rsync -avz --progress \
  backend/main.py backend/routes.py backend/config.py backend/models.py \
  backend/data_fetchers.py backend/ml_model.py backend/scoring.py \
  backend/cache.py backend/nibrs_data.py backend/city_crime_loader.py \
  backend/fbi_cde_loader.py backend/requirements.txt \
  lumos@YOUR_SERVER_IP:/home/lumos/lumos/backend/

# If you retrained the model:
rsync -avz --progress backend/safety_model_xgb.ubj lumos@YOUR_SERVER_IP:/home/lumos/lumos/backend/

# If you updated datasets:
rsync -avz --progress datasets/agency_profiles.json datasets/state_temporal_profiles.json \
  datasets/city_crime_lookup.json datasets/college_crime_lookup.json \
  datasets/county_crime_lookup.json \
  lumos@YOUR_SERVER_IP:/home/lumos/lumos/datasets/

# Then on the server, restart:
ssh lumos@YOUR_SERVER_IP "sudo systemctl restart lumos-api"
```

### 18.4 Update Python Packages

```bash
ssh lumos@YOUR_SERVER_IP
source /home/lumos/lumos/venv/bin/activate
pip install --upgrade -r /home/lumos/lumos/backend/requirements.txt
sudo systemctl restart lumos-api
```

### 18.5 Monitor Memory Usage

Each Gunicorn worker loads:

- XGBoost model: ~50 MB
- Agency profiles JSON: ~40 MB in parsed Python dicts
- State profiles: ~2 MB
- City/college/county lookups: ~15 MB
- **Total per worker: ~150-200 MB**

With 2 workers + system overhead, expect **~600 MB - 1 GB RAM usage**.

```bash
# Check memory
free -h

# Check process memory
ps aux | grep gunicorn

# Monitor in real-time
htop
```

### 18.6 Log Rotation

Create `/etc/logrotate.d/lumos-api`:

```bash
sudo nano /etc/logrotate.d/lumos-api
```

```
/home/lumos/lumos/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0644 lumos lumos
    postrotate
        systemctl reload lumos-api > /dev/null 2>&1 || true
    endscript
}
```

---

## 19. Troubleshooting

### "XGBoost model not found — using fallback"

The `safety_model_xgb.ubj` file is missing from `/home/lumos/lumos/backend/`. Re-upload it:

```bash
scp backend/safety_model_xgb.ubj lumos@YOUR_SERVER_IP:/home/lumos/lumos/backend/
```

### "agency_profiles.json not found"

The NIBRS data pipeline can't find datasets. Check that `nibrs_data.py` resolves the path correctly. It uses:

```python
_DATASETS_BASE = Path(__file__).resolve().parent.parent / "datasets"
```

This means it expects `datasets/` to be at `/home/lumos/lumos/datasets/` (sibling of `backend/`).

Verify:

```bash
ls /home/lumos/lumos/datasets/agency_profiles.json
```

### "Config can't find .env"

`config.py` loads `.env` from:

```python
_env_path = Path(__file__).resolve().parent.parent / ".env"
```

So `.env` must be at `/home/lumos/lumos/.env`.

Verify:

```bash
ls -la /home/lumos/lumos/.env
```

### Rate limiting / "429 Too Many Requests"

The backend has an in-memory rate limiter at 30 req/min/IP (in `routes.py`). Behind Nginx, all requests appear to come from `127.0.0.1` unless you pass `X-Real-IP`. This is already configured in the Nginx config above with `proxy_set_header X-Real-IP $remote_addr`.

However, FastAPI's `request.client.host` won't automatically read `X-Real-IP`. To fix this, add the `--proxy-headers` flag to Uvicorn or install `uvicorn[standard]` and add this to `main.py` or configure Gunicorn:

```bash
# In gunicorn.conf.py, add:
forwarded_allow_ips = "127.0.0.1"
```

And update the rate limiter in `routes.py` to read the forwarded IP:

```python
client_ip = request.headers.get("X-Real-IP", request.client.host if request.client else "unknown")
```

### Gemini API fails

Gemini refinement is best-effort — if it fails, the score falls back to ML-only. Check:

```bash
grep -i "gemini" /home/lumos/lumos/logs/error.log
```

Common issue: the env var is `VITE_GEMINI_API_KEY` (shared with frontend), loaded in `config.py` as `GEMINI_API_KEY = os.environ.get("VITE_GEMINI_API_KEY", "")`.

### Server runs out of RAM

If you see OOM kills:

1. Reduce workers in `gunicorn.conf.py` from 2 to 1
2. Or upgrade your Vultr plan to 4 GB RAM
3. Add swap space as a safety net:
   ```bash
   sudo fallocate -l 2G /swapfile
   sudo chmod 600 /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile
   echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
   ```

### Checking which external APIs are being called

Your `data_fetchers.py` makes outbound HTTP calls to:

- `https://api.usa.gov/crime/fbi/cde` (FBI CDE)
- `https://maps.googleapis.com/maps/api/` (Google Maps Geocode/Places)
- `https://places.googleapis.com/v1/` (Google Places New API)
- `https://api.weather.gov/` (NWS)
- `https://geocoding.geo.census.gov/` (Census)
- `https://data.cityofchicago.org/`, `data.cityofnewyork.us/`, etc. (Socrata)
- `https://app.ticketmaster.com/` (Ticketmaster)
- `https://api.astronomyapi.com/` (Moon data)
- `https://api.openweathermap.org/` (Weather)
- `https://citizen.com/api/` (Citizen incidents)
- `https://api.crimeometer.com/` (Crimeometer)

All of these should be reachable from a Vultr server (no special firewall rules needed for outbound).

---

## Quick Reference: Complete Command Sequence

For copy-paste convenience, here's the entire server setup in one block (after SSH-ing in as root):

```bash
# ── As root ──
adduser lumos
usermod -aG sudo lumos
mkdir -p /home/lumos/.ssh
cp ~/.ssh/authorized_keys /home/lumos/.ssh/
chown -R lumos:lumos /home/lumos/.ssh
chmod 700 /home/lumos/.ssh && chmod 600 /home/lumos/.ssh/authorized_keys
apt update && apt upgrade -y
apt install -y build-essential curl wget git unzip software-properties-common nginx certbot python3-certbot-nginx libopenblas-dev liblapack-dev gfortran
add-apt-repository ppa:deadsnakes/ppa -y
apt update && apt install -y python3.12 python3.12-venv python3.12-dev
ufw default deny incoming && ufw default allow outgoing
ufw allow 22/tcp && ufw allow 80/tcp && ufw allow 443/tcp
ufw enable

# ── Switch to lumos user ──
su - lumos

# ── After rsync-ing files into /home/lumos/lumos/ ──
cd /home/lumos/lumos
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r backend/requirements.txt
pip install gunicorn uvicorn[standard]
mkdir -p logs

# ── Test ──
cd backend && python main.py
# Ctrl+C after verifying

# ── Set up gunicorn.conf.py, systemd service, nginx config per sections 10-12 ──
# ── Then: ──
sudo systemctl daemon-reload
sudo systemctl enable lumos-api && sudo systemctl start lumos-api
sudo systemctl restart nginx
```

---

## Cost Estimate

| Resource                                            | Monthly Cost            |
| --------------------------------------------------- | ----------------------- |
| Vultr Cloud Compute (2 vCPU / 4 GB RAM / 80 GB SSD) | $24                     |
| Domain name (optional, e.g., Cloudflare)            | $10-15/year             |
| SSL certificate (Let's Encrypt)                     | Free                    |
| External APIs (Google Maps, Gemini, etc.)           | Depends on usage        |
| **Total**                                     | **~$24-30/month** |

---

*Last updated: February 2026*
