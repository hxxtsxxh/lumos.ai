"""
Lumos Safety Backend — FastAPI + XGBoost
Modular entry point. All logic is split across:
  config.py, models.py, data_fetchers.py, ml_model.py, scoring.py, routes.py, cache.py
"""

import logging

logging.basicConfig(level=logging.INFO)

# Import the FastAPI app from routes (this also triggers model loading)
from routes import app  # noqa: F401

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
