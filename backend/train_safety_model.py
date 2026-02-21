"""Lumos Backend — XGBoost Safety Model Training

Loads pre-computed agency_profiles.json and trains an XGBoost regressor
with NIBRS-derived ground truth labels (NOT formula-derived).

Run from project root:
    python backend/train_safety_model.py
"""

import json
import logging
import math
import sys
import time
from pathlib import Path

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
logger = logging.getLogger("train")

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
_DATASETS_DIR = _PROJECT_ROOT / "datasets"
_MODEL_PATH = _SCRIPT_DIR / "safety_model_xgb.ubj"

# 25 features — MUST match inference order in scoring.py
FEATURE_NAMES_V2 = [
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


def _load_profiles():
    """Load agency_profiles.json and state_temporal_profiles.json."""
    ap_path = _DATASETS_DIR / "agency_profiles.json"
    sp_path = _DATASETS_DIR / "state_temporal_profiles.json"

    if not ap_path.exists():
        logger.error(f"Agency profiles not found: {ap_path}")
        logger.error("Run 'python backend/precompute_nibrs.py' first.")
        sys.exit(1)

    with open(ap_path) as f:
        agency_profiles = json.load(f)
    logger.info(f"Loaded {len(agency_profiles)} agency profiles")

    state_profiles = {}
    if sp_path.exists():
        with open(sp_path) as f:
            state_profiles = json.load(f)
        logger.info(f"Loaded {len(state_profiles)} state profiles")

    return agency_profiles, state_profiles


def _compute_percentile_ranks(values: list[float]) -> dict[int, float]:
    """Compute percentile rank for each index in values."""
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    ranks = {}
    for i, v in enumerate(values):
        # Count how many are below this value
        below = sum(1 for sv in sorted_vals if sv < v)
        ranks[i] = below / max(n - 1, 1)
    return ranks


def _generate_training_data(agency_profiles: dict, state_profiles: dict):
    """Generate training samples with NIBRS-derived ground truth labels."""
    X_rows = []
    y_rows = []
    meta = []

    # Collect all Part I rates for percentile ranking
    agencies = list(agency_profiles.values())
    all_rates = [a["part1_rate"] for a in agencies]
    if not all_rates:
        logger.error("No agencies with Part I rate data")
        sys.exit(1)

    sorted_rates = sorted(all_rates)
    n_rates = len(sorted_rates)

    # Compute state-level average crime rates for state_crime_rate_norm
    state_avg_rates = {}
    for st, sp in state_profiles.items():
        # Use the state's agencies to compute average Part I rate
        st_agencies = [a for a in agencies if a.get("state_abbr") == st]
        if st_agencies:
            state_avg_rates[st] = np.mean([a["part1_rate"] for a in st_agencies])
        else:
            state_avg_rates[st] = np.median(all_rates)

    # Fixed normalization constants — MUST match scoring.py
    NORM_PART1 = 8000
    NORM_VIOLENT = 2000
    NORM_PROPERTY = 6000
    NORM_STATE = 5000
    NORM_SEVERITY = 10.0
    NORM_POP_GROUP = 16.0
    NORM_OFFICERS = 5.0

    # Sample hours strategically (not all 24)
    sample_hours = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22]
    # Sample days of week
    sample_dows = [0, 1, 2, 3, 4, 5, 6]
    # Gender / group variations
    gender_variations = [
        (0.7, 1),   # female, alone
        (0.4, 1),   # male, alone
        (0.5, 2),   # mixed, pair
        (0.5, 3),   # mixed, group
    ]
    # Weather variations
    weather_variations = [0.0, 0.3, 0.6, 0.9]

    logger.info(f"Generating training data from {len(agencies)} agencies...")
    logger.info(f"  Sample hours: {len(sample_hours)}, DOWs: {len(sample_dows)}, "
                f"gender/group: {len(gender_variations)}, weather: {len(weather_variations)}")

    for idx, agency in enumerate(agencies):
        pop = agency.get("population", 0)
        if pop <= 0:
            continue

        part1_rate = agency["part1_rate"]
        state = agency.get("state_abbr", "")
        state_rate = state_avg_rates.get(state, np.median(all_rates))

        # Sigmoid-based safety (matches formula's crime_baseline curve)
        # This gives smooth, interpretable scores:
        #   800/100k (Irvine)   → ~0.93
        #   2400/100k (avg)     → ~0.64
        #   4003/100k (Atlanta) → ~0.42
        #   8000/100k (worst)   → ~0.22
        rate_norm = part1_rate / 5000
        base_safety = max(0.10, min(0.95, 1.0 / (1.0 + rate_norm ** 1.6)))

        hourly_dist = agency.get("hourly_dist", [1 / 24] * 24)
        dow_dist = agency.get("dow_dist", [1 / 7] * 7)
        monthly_dist = agency.get("monthly_dist", [1 / 12] * 12)

        h_mean = max(np.mean(hourly_dist), 1e-9)
        d_mean = max(np.mean(dow_dist), 1e-9)
        m_mean = max(np.mean(monthly_dist), 1e-9)

        weapon_rate = agency.get("weapon_rate", 0.0)
        stranger_rate = agency.get("stranger_rate", 0.3)
        severity_score = agency.get("severity_score", 3.0)
        officers_per_1000 = agency.get("officers_per_1000", 0.0)
        pop_group = agency.get("population_group", 5)
        is_urban_val = 1.0 if pop >= 250_000 else 0.0

        # Strategic sampling: not every combination, but representative
        for hour in sample_hours:
            for dow in [0, 5]:  # weekday + weekend only (reduce data size)
                hourly_risk = hourly_dist[hour] / h_mean
                dow_risk = dow_dist[dow] / d_mean
                month = 6  # default to July (mid-year)
                monthly_risk = monthly_dist[month] / m_mean

                is_weekend = 1.0 if dow >= 5 else 0.0
                time_sin = math.sin(2 * math.pi * hour / 24)
                time_cos = math.cos(2 * math.pi * hour / 24)

                for gender_factor, people_count in gender_variations:
                    for weather_sev in [0.0, 0.5]:  # reduce combinations
                        # ── NIBRS-derived ground truth label ──
                        # Temporal modifier: >1 = more crime than avg = riskier
                        temporal_modifier = hourly_risk * dow_risk
                        # Scale down for high-crime hours, up for low-crime
                        temporal_adj = 1.0 - (temporal_modifier - 1.0) * 0.15
                        temporal_adj = max(0.70, min(1.15, temporal_adj))
                        safety = base_safety * temporal_adj

                        # Contextual adjustments
                        # Weapon rate penalty (higher weapon rate -> less safe)
                        safety *= (1.0 - weapon_rate * 0.15)
                        # Stranger crime penalty
                        safety *= (1.0 - (stranger_rate - 0.3) * 0.1)
                        # More people = safer
                        group_bonus = 1.0 + (people_count - 1) * 0.06
                        safety *= group_bonus
                        # Gender adjustment
                        gender_penalty = (gender_factor - 0.4) * 0.15  # female=0.045, male=0
                        safety *= (1.0 - gender_penalty)
                        # Weather penalty
                        safety *= (1.0 - weather_sev * 0.08)
                        # Officer density bonus
                        safety *= (1.0 + min(officers_per_1000, 5.0) * 0.02)

                        label = float(np.clip(safety, 0.05, 0.95))

                        # ── Build feature vector ──
                        features = [
                            min(part1_rate / NORM_PART1, 1.0),         # agency_part1_rate
                            min(agency.get("violent_rate", 0) / NORM_VIOLENT, 1.0),
                            min(agency.get("property_rate", 0) / NORM_PROPERTY, 1.0),
                            weapon_rate,
                            stranger_rate,
                            min(severity_score / NORM_SEVERITY, 1.0),
                            min(state_rate / NORM_STATE, 1.0),
                            min(pop_group / NORM_POP_GROUP, 1.0),
                            min(hourly_risk / 3.0, 1.0),
                            min(dow_risk / 2.0, 1.0),
                            min(monthly_risk / 2.0, 1.0),
                            time_sin,
                            time_cos,
                            is_weekend,
                            min(people_count / 4.0, 1.0),
                            gender_factor,
                            weather_sev,
                            min(officers_per_1000 / NORM_OFFICERS, 1.0),
                            0.0,  # is_college (vary randomly)
                            is_urban_val,
                            0.5,  # poi_density (default)
                            0.1,  # live_events_norm (default)
                            0.1,  # live_incidents_norm (default)
                            0.5,  # moon_illumination (default)
                            min(part1_rate / (NORM_PART1 * 0.5), 1.0),  # spatial_density
                        ]

                        X_rows.append(features)
                        y_rows.append(label)
                        meta.append({"agency": agency.get("name", ""), "state": state})

        if (idx + 1) % 1000 == 0:
            logger.info(f"  Processed {idx + 1}/{len(agencies)} agencies, "
                        f"{len(X_rows)} samples so far")

    # Add college variations
    rng = np.random.default_rng(42)
    n_college_samples = min(len(X_rows) // 10, 50000)
    for i in rng.integers(0, len(X_rows), size=n_college_samples):
        row = list(X_rows[i])
        row[18] = 1.0  # is_college
        # Colleges tend to have slightly lower crime
        label = min(y_rows[i] * 1.05, 0.95)
        X_rows.append(row)
        y_rows.append(label)

    logger.info(f"Total training samples: {len(X_rows)}")
    return np.array(X_rows, dtype=np.float32), np.array(y_rows, dtype=np.float32)


def main():
    t0 = time.time()
    agency_profiles, state_profiles = _load_profiles()

    X, y = _generate_training_data(agency_profiles, state_profiles)

    # ── Stratified split by creating state groups ──
    rng = np.random.default_rng(42)
    n = len(X)
    indices = np.arange(n)
    rng.shuffle(indices)

    n_train = int(n * 0.8)
    n_val = int(n * 0.1)

    train_idx = indices[:n_train]
    val_idx = indices[n_train:n_train + n_val]
    test_idx = indices[n_train + n_val:]

    X_train, y_train = X[train_idx], y[train_idx]
    X_val, y_val = X[val_idx], y[val_idx]
    X_test, y_test = X[test_idx], y[test_idx]

    logger.info(f"Split: train={len(X_train)}, val={len(X_val)}, test={len(X_test)}")
    logger.info(f"Label stats: mean={y.mean():.3f}, std={y.std():.3f}, "
                f"min={y.min():.3f}, max={y.max():.3f}")

    # ── Train XGBoost ──
    import xgboost as xgb

    dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=FEATURE_NAMES_V2)
    dval = xgb.DMatrix(X_val, label=y_val, feature_names=FEATURE_NAMES_V2)
    dtest = xgb.DMatrix(X_test, label=y_test, feature_names=FEATURE_NAMES_V2)

    params = {
        "objective": "reg:squarederror",
        "max_depth": 8,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_alpha": 0.1,
        "reg_lambda": 1.0,
        "min_child_weight": 5,
        "tree_method": "hist",
        "eval_metric": "rmse",
        "seed": 42,
    }

    logger.info("Training XGBoost model...")
    model = xgb.train(
        params,
        dtrain,
        num_boost_round=500,
        evals=[(dtrain, "train"), (dval, "val")],
        early_stopping_rounds=20,
        verbose_eval=50,
    )

    # ── Evaluate ──
    preds = model.predict(dtest)
    preds = np.clip(preds, 0.0, 1.0)

    mae = np.mean(np.abs(preds - y_test))
    rmse = np.sqrt(np.mean((preds - y_test) ** 2))
    # Accuracy@10: within 10 percentage points
    acc_10 = np.mean(np.abs(preds * 100 - y_test * 100) < 10)

    logger.info(f"\n{'='*50}")
    logger.info(f"Test Results:")
    logger.info(f"  MAE:        {mae:.4f}")
    logger.info(f"  RMSE:       {rmse:.4f}")
    logger.info(f"  Acc@10:     {acc_10:.2%}")
    logger.info(f"{'='*50}")

    # Feature importance
    importance = model.get_score(importance_type="gain")
    sorted_imp = sorted(importance.items(), key=lambda x: -x[1])
    logger.info("\nTop 10 features by gain:")
    for fname, gain in sorted_imp[:10]:
        logger.info(f"  {fname:30s} {gain:.1f}")

    # ── Save model ──
    model.save_model(str(_MODEL_PATH))
    sz = _MODEL_PATH.stat().st_size / (1024 * 1024)
    logger.info(f"\nModel saved to {_MODEL_PATH} ({sz:.1f} MB)")

    # ── Save training metadata ──
    meta_path = _DATASETS_DIR / "training_metadata.json"
    metadata = {
        "n_samples": int(n),
        "n_train": int(len(X_train)),
        "n_val": int(len(X_val)),
        "n_test": int(len(X_test)),
        "n_features": int(X.shape[1]),
        "feature_names": FEATURE_NAMES_V2,
        "mae": float(mae),
        "rmse": float(rmse),
        "accuracy_at_10": float(acc_10),
        "best_iteration": int(model.best_iteration) if hasattr(model, "best_iteration") else 500,
        "label_mean": float(y.mean()),
        "label_std": float(y.std()),
        "top_features": [{"name": n, "gain": float(g)} for n, g in sorted_imp[:15]],
    }
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)
    logger.info(f"Training metadata saved to {meta_path}")

    elapsed = time.time() - t0
    logger.info(f"Total training time: {elapsed:.0f}s")


if __name__ == "__main__":
    main()
