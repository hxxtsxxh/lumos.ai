"""Lumos Backend — XGBoost Safety Model (v2)

Loads a pre-trained XGBoost model from safety_model_xgb.ubj.
Training is done offline via train_safety_model.py.

The model predicts a safety score (0-1) given 25 input features.
See config.FEATURE_NAMES for the full list.
"""

import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger("lumos.model")

_MODEL_PATH = Path(__file__).resolve().parent / "safety_model_xgb.ubj"


class _FallbackModel:
    """Returns a constant safety score when no trained model is available."""

    def predict(self, X, **kwargs):
        n = X.shape[0] if hasattr(X, "shape") else len(X)
        return 0.65 * np.ones((n, 1), dtype=np.float32)


class _ModelProxy:
    """Lazy-load the XGBoost model on first use, not at import time."""

    def __init__(self):
        self._model = None

    def _ensure_loaded(self):
        if self._model is not None:
            return
        if _MODEL_PATH.exists():
            try:
                import xgboost as xgb
                booster = xgb.Booster()
                booster.load_model(str(_MODEL_PATH))
                self._model = booster
                logger.info(f"XGBoost model loaded from {_MODEL_PATH}")
            except Exception as e:
                logger.warning(f"Failed to load XGBoost model: {e}")
                self._model = _FallbackModel()
        else:
            logger.warning(
                f"XGBoost model not found at {_MODEL_PATH} — using fallback. "
                "Run 'python backend/train_safety_model.py' to train."
            )
            self._model = _FallbackModel()

    def predict(self, X, **kwargs):
        """Predict safety scores. Returns ndarray shape (n, 1) in [0, 1]."""
        self._ensure_loaded()
        if isinstance(self._model, _FallbackModel):
            return self._model.predict(X)
        import xgboost as xgb
        from config import FEATURE_NAMES
        if not isinstance(X, np.ndarray):
            X = np.array(X, dtype=np.float32)
        dmat = xgb.DMatrix(X, feature_names=FEATURE_NAMES)
        preds = self._model.predict(dmat)
        preds = np.clip(preds, 0.0, 1.0).reshape(-1, 1)
        return preds


# Lazy proxy — model loads on first prediction, not at import
safety_model = _ModelProxy()

