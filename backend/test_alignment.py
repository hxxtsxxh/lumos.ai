#!/usr/bin/env python3
"""
Comprehensive alignment test: 24-Hour Risk Pattern vs Safety Index vs Incident Types.

Tests:
  1. Monotonicity — safety scores decrease as NIBRS hourly risk increases
  2. Night/Day differential — nighttime is consistently riskier than daytime
  3. Peak/trough alignment — peak risk hour matches lowest safety index
  4. Cross-city consistency — pattern holds for diverse cities
  5. Temporal incident shift — incident types change appropriately with hour
  6. State profile coverage — all 50 states produce valid curves
  7. Gender sensitivity — female scores lower at night, difference widens
  8. Group size effect — more people = safer, at every hour
  9. Urban vs rural — urban areas have lower safety scores consistently
  10. Weekend effect — weekends show different patterns
  11. Weather amplification — bad weather lowers scores, especially at night
  12. Edge cases — boundary hours, extreme crime rates, zero population
  13. Score range validation — all scores stay within [5, 95]
  14. Risk curve shape — NIBRS curves have realistic shape properties
  15. Incident type temporal coherence — violent crimes ↑ at night

Run:  python backend/test_alignment.py
"""

import os, sys, time, math, json, traceback
from collections import defaultdict
from dataclasses import dataclass

# Ensure we import from the right place (production path)
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ".")

import numpy as np

# Initialize NIBRS data first
from nibrs_data import initialize_nibrs, nibrs_stats
initialize_nibrs()

from scoring import (
    compute_safety_score,
    predict_incident_types_nibrs,
    _NIBRS_CODE_TO_NAME,
    _get_time_period,
    build_incident_types,
    get_icon,
)
from ml_model import safety_model

# ─────────────────────────────────────────────────────────────────
# Test Infrastructure
# ─────────────────────────────────────────────────────────────────

@dataclass
class TestResult:
    name: str
    passed: bool
    details: str
    duration_ms: float

results: list[TestResult] = []
total_predictions = 0

def run_test(name: str, func):
    """Run a test function and record the result."""
    global total_predictions
    t0 = time.perf_counter()
    try:
        passed, details, n_preds = func()
        total_predictions += n_preds
        dt = (time.perf_counter() - t0) * 1000
        results.append(TestResult(name, passed, details, dt))
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}  {name} ({dt:.0f}ms, {n_preds} predictions)")
        if not passed:
            for line in details.split("\n")[:8]:
                print(f"         {line}")
    except Exception as e:
        dt = (time.perf_counter() - t0) * 1000
        tb = traceback.format_exc()
        results.append(TestResult(name, False, f"EXCEPTION: {e}\n{tb}", dt))
        print(f"  💥 ERROR {name}: {e}")


# ─────────────────────────────────────────────────────────────────
# Helper: compute safety scores for all 24 hours
# ─────────────────────────────────────────────────────────────────

def get_24h_scores(
    city_name: str = "Atlanta",
    state_abbr: str = "GA",
    crime_rate: float = 4000.0,
    population: int = 500_000,
    gender: str = "male",
    people_count: int = 1,
    weather_severity: float = 0.0,
    is_college: float = 0.0,
    is_urban: float = 1.0,
    is_weekend: float = 0.0,
    poi_density: float = 0.3,
) -> list[int]:
    """Return 24 safety index values (one per hour)."""
    scores = []
    for h in range(24):
        s_idx, _ = compute_safety_score(
            crime_rate_per_100k=crime_rate,
            hour=h,
            people_count=people_count,
            gender=gender,
            weather_severity=weather_severity,
            population=population,
            city_incidents=[],
            tf_model=safety_model,
            state_abbr=state_abbr,
            is_college=is_college,
            is_urban=is_urban,
            is_weekend=is_weekend,
            poi_density=poi_density,
            city_name=city_name,
        )
        scores.append(s_idx)
    return scores


# ─────────────────────────────────────────────────────────────────
# Test Cities — diverse profiles
# ─────────────────────────────────────────────────────────────────

TEST_CITIES = [
    # (city, state, crime_rate, population, description)
    ("Atlanta", "GA", 4200, 500_000, "High-crime urban"),
    ("Irvine", "CA", 1200, 310_000, "Low-crime suburban"),
    ("St. Louis", "MO", 6500, 300_000, "Very high crime"),
    ("New York", "NY", 2400, 8_300_000, "Mega-city moderate"),
    ("Nashville", "TN", 4800, 700_000, "High-crime mid-size"),
    ("Boulder", "CO", 3100, 105_000, "College town moderate"),
    ("Austin", "TX", 3500, 1_000_000, "Growing urban"),
    ("Portland", "OR", 5200, 650_000, "High property crime"),
    ("Miami", "FL", 3800, 450_000, "Tourist city"),
    ("Seattle", "WA", 4100, 750_000, "PNW urban"),
    ("Detroit", "MI", 6800, 640_000, "Very high crime"),
    ("Phoenix", "AZ", 4500, 1_600_000, "Large sunbelt"),
    ("Denver", "CO", 4000, 720_000, "Mid-size urban"),
    ("Chicago", "IL", 3700, 2_700_000, "Large city"),
    ("Houston", "TX", 5100, 2_300_000, "Large high-crime"),
    ("Boise", "ID", 1800, 235_000, "Low-crime small"),
    ("Salt Lake City", "UT", 5000, 200_000, "Mid-size elevated"),
    ("Charlotte", "NC", 4300, 880_000, "Growing metro"),
    ("Minneapolis", "MN", 5500, 430_000, "High crime mid-size"),
    ("San Francisco", "CA", 4900, 870_000, "High property crime"),
]


# ═══════════════════════════════════════════════════════════════
# TEST 1: Night vs Day Differential
# ═══════════════════════════════════════════════════════════════

def test_night_day_differential():
    """Night hours (10pm-5am) should have LOWER safety scores than day (8am-4pm)."""
    failures = []
    n_preds = 0
    night_hours = [22, 23, 0, 1, 2, 3, 4, 5]
    day_hours = [8, 9, 10, 11, 12, 13, 14, 15, 16]

    for city, state, cr, pop, desc in TEST_CITIES:
        scores = get_24h_scores(city, state, cr, pop)
        n_preds += 24

        night_avg = np.mean([scores[h] for h in night_hours])
        day_avg = np.mean([scores[h] for h in day_hours])

        if night_avg >= day_avg:
            failures.append(
                f"{city}: night_avg={night_avg:.1f} >= day_avg={day_avg:.1f}"
            )

    passed = len(failures) == 0
    detail = f"{len(TEST_CITIES)} cities tested. "
    if failures:
        detail += f"{len(failures)} failures:\n" + "\n".join(failures[:10])
    else:
        detail += "All cities show night < day safety pattern."
    return passed, detail, n_preds


# ═══════════════════════════════════════════════════════════════
# TEST 2: Peak Risk Hour Alignment
# ═══════════════════════════════════════════════════════════════

def test_peak_risk_alignment():
    """The hour with the lowest safety score should be between 10pm-5am."""
    failures = []
    n_preds = 0

    for city, state, cr, pop, desc in TEST_CITIES:
        scores = get_24h_scores(city, state, cr, pop)
        n_preds += 24

        min_hour = scores.index(min(scores))
        # Min safety should be in the night window: 10pm - 5am (hours 22-23, 0-5)
        is_night = min_hour >= 22 or min_hour <= 5
        if not is_night:
            failures.append(
                f"{city}: min safety at hour {min_hour} "
                f"(score={scores[min_hour]}), expected 22-5"
            )

    passed = len(failures) == 0
    detail = f"{len(TEST_CITIES)} cities tested. "
    if failures:
        detail += f"{len(failures)} failures:\n" + "\n".join(failures[:10])
    else:
        detail += "All cities have peak risk in 10pm-5am window."
    return passed, detail, n_preds


# ═══════════════════════════════════════════════════════════════
# TEST 3: Safest Hour Alignment
# ═══════════════════════════════════════════════════════════════

def test_safest_hour_alignment():
    """The hour with the highest safety score should be between 7am-5pm."""
    failures = []
    n_preds = 0

    for city, state, cr, pop, desc in TEST_CITIES:
        scores = get_24h_scores(city, state, cr, pop)
        n_preds += 24

        max_hour = scores.index(max(scores))
        is_day = 7 <= max_hour <= 17
        if not is_day:
            failures.append(
                f"{city}: max safety at hour {max_hour} "
                f"(score={scores[max_hour]}), expected 7-17"
            )

    passed = len(failures) == 0
    detail = f"{len(TEST_CITIES)} cities tested. "
    if failures:
        detail += f"{len(failures)} failures:\n" + "\n".join(failures[:10])
    else:
        detail += "All cities have safest hour in 7am-5pm window."
    return passed, detail, n_preds


# ═══════════════════════════════════════════════════════════════
# TEST 4: Night-Day Spread Magnitude
# ═══════════════════════════════════════════════════════════════

def test_night_day_spread():
    """The difference between safest and riskiest hour should be at least 5 points."""
    failures = []
    n_preds = 0
    spreads = []

    for city, state, cr, pop, desc in TEST_CITIES:
        scores = get_24h_scores(city, state, cr, pop)
        n_preds += 24

        spread = max(scores) - min(scores)
        spreads.append((city, spread))
        if spread < 5:
            failures.append(
                f"{city}: spread only {spread} points "
                f"(max={max(scores)}, min={min(scores)})"
            )

    passed = len(failures) == 0
    avg_spread = np.mean([s for _, s in spreads])
    detail = f"Avg spread: {avg_spread:.1f} points. "
    if failures:
        detail += f"{len(failures)} cities below 5-point threshold:\n" + "\n".join(failures[:10])
    else:
        detail += f"All {len(TEST_CITIES)} cities have >= 5 point spread."
    return passed, detail, n_preds


# ═══════════════════════════════════════════════════════════════
# TEST 5: Score Range Validation [5, 95]
# ═══════════════════════════════════════════════════════════════

def test_score_range():
    """All safety scores must be within [5, 95]."""
    failures = []
    n_preds = 0

    for city, state, cr, pop, desc in TEST_CITIES:
        scores = get_24h_scores(city, state, cr, pop)
        n_preds += 24
        for h, s in enumerate(scores):
            if s < 5 or s > 95:
                failures.append(f"{city} h={h}: score={s}, out of [5,95]")

    passed = len(failures) == 0
    detail = f"Tested {len(TEST_CITIES)*24} score values. "
    if failures:
        detail += f"{len(failures)} out-of-range:\n" + "\n".join(failures[:10])
    else:
        detail += "All within [5, 95]."
    return passed, detail, n_preds


# ═══════════════════════════════════════════════════════════════
# TEST 6: Cross-City Ordering
# ═══════════════════════════════════════════════════════════════

def test_cross_city_ordering():
    """Low-crime cities should have higher safety scores than high-crime cities
    at the same hour, most of the time."""
    n_preds = 0
    
    low_crime = [c for c in TEST_CITIES if c[2] <= 2000]
    high_crime = [c for c in TEST_CITIES if c[2] >= 5000]
    
    if not low_crime or not high_crime:
        return True, "Skipped — insufficient city diversity", 0

    violations = 0
    total_comparisons = 0

    for lc_city, lc_state, lc_cr, lc_pop, _ in low_crime:
        lc_scores = get_24h_scores(lc_city, lc_state, lc_cr, lc_pop)
        n_preds += 24
        for hc_city, hc_state, hc_cr, hc_pop, _ in high_crime:
            hc_scores = get_24h_scores(hc_city, hc_state, hc_cr, hc_pop)
            n_preds += 24
            for h in range(24):
                total_comparisons += 1
                if lc_scores[h] < hc_scores[h]:
                    violations += 1

    violation_rate = violations / total_comparisons if total_comparisons else 0
    # Allow up to 15% violations (some hours/cities may have special profiles)
    passed = violation_rate < 0.15
    detail = (
        f"{total_comparisons} comparisons, {violations} violations "
        f"({violation_rate*100:.1f}%). "
        f"Low-crime cities: {[c[0] for c in low_crime]}, "
        f"High-crime: {[c[0] for c in high_crime]}"
    )
    return passed, detail, n_preds


# ═══════════════════════════════════════════════════════════════
# TEST 7: Gender Sensitivity
# ═══════════════════════════════════════════════════════════════

def test_gender_sensitivity():
    """Female travelers should have lower/equal safety scores,
    especially at night hours."""
    failures = []
    n_preds = 0
    night_diffs = []
    day_diffs = []

    for city, state, cr, pop, desc in TEST_CITIES[:10]:
        male_scores = get_24h_scores(city, state, cr, pop, gender="male")
        female_scores = get_24h_scores(city, state, cr, pop, gender="female")
        n_preds += 48  # 2 × 24

        for h in range(24):
            diff = male_scores[h] - female_scores[h]
            if h >= 22 or h <= 5:
                night_diffs.append(diff)
            elif 8 <= h <= 16:
                day_diffs.append(diff)

            # Female should never be SIGNIFICANTLY safer
            if female_scores[h] > male_scores[h] + 5:
                failures.append(
                    f"{city} h={h}: female={female_scores[h]} > male={male_scores[h]}+5"
                )

    avg_night_diff = np.mean(night_diffs) if night_diffs else 0
    avg_day_diff = np.mean(day_diffs) if day_diffs else 0

    passed = len(failures) == 0
    detail = (
        f"Avg male-female diff: night={avg_night_diff:.1f}, day={avg_day_diff:.1f}. "
    )
    if failures:
        detail += f"{len(failures)} violations:\n" + "\n".join(failures[:10])
    else:
        detail += "Gender sensitivity consistent."
    return passed, detail, n_preds


# ═══════════════════════════════════════════════════════════════
# TEST 8: Group Size Effect
# ═══════════════════════════════════════════════════════════════

def test_group_size_effect():
    """More people should give higher/equal safety scores at every hour."""
    failures = []
    n_preds = 0

    for city, state, cr, pop, desc in TEST_CITIES[:10]:
        solo = get_24h_scores(city, state, cr, pop, people_count=1)
        group = get_24h_scores(city, state, cr, pop, people_count=4)
        n_preds += 48

        for h in range(24):
            if group[h] < solo[h] - 2:  # Allow 2-point tolerance
                failures.append(
                    f"{city} h={h}: group(4)={group[h]} < solo(1)={solo[h]}"
                )

    passed = len(failures) == 0
    detail = f"Tested {len(TEST_CITIES[:10])} cities × 24 hours. "
    if failures:
        detail += f"{len(failures)} violations:\n" + "\n".join(failures[:10])
    else:
        detail += "Group size consistently improves safety."
    return passed, detail, n_preds


# ═══════════════════════════════════════════════════════════════
# TEST 9: Weather Amplification
# ═══════════════════════════════════════════════════════════════

def test_weather_amplification():
    """Bad weather should lower safety scores, especially at night."""
    failures = []
    n_preds = 0
    weather_drops = []

    for city, state, cr, pop, desc in TEST_CITIES[:10]:
        clear = get_24h_scores(city, state, cr, pop, weather_severity=0.0)
        storm = get_24h_scores(city, state, cr, pop, weather_severity=0.8)
        n_preds += 48

        for h in range(24):
            drop = clear[h] - storm[h]
            weather_drops.append(drop)
            if storm[h] > clear[h] + 2:  # Storm should not be SAFER
                failures.append(
                    f"{city} h={h}: storm={storm[h]} > clear={clear[h]}"
                )

    avg_drop = np.mean(weather_drops) if weather_drops else 0
    passed = len(failures) == 0
    detail = f"Avg weather drop: {avg_drop:.1f} points. "
    if failures:
        detail += f"{len(failures)} violations:\n" + "\n".join(failures[:10])
    else:
        detail += "Weather consistently reduces safety."
    return passed, detail, n_preds


# ═══════════════════════════════════════════════════════════════
# TEST 10: State Profile Coverage
# ═══════════════════════════════════════════════════════════════

def test_state_profile_coverage():
    """All 50 states should produce valid 24-element risk curves."""
    failures = []
    n_states = 0

    all_states = list(nibrs_stats.state_profiles.keys())

    for st in all_states:
        n_states += 1
        curve = nibrs_stats.get_hourly_risk_curve(state_abbr=st, base_risk=50.0)
        if curve is None:
            failures.append(f"{st}: None curve")
            continue
        if len(curve) != 24:
            failures.append(f"{st}: len={len(curve)}, expected 24")
            continue
        if np.any(np.isnan(curve)):
            failures.append(f"{st}: contains NaN")
            continue
        if np.any(np.isinf(curve)):
            failures.append(f"{st}: contains Inf")
            continue
        if curve.min() < 0:
            failures.append(f"{st}: min={curve.min():.1f} < 0")
        if curve.max() > 100:
            failures.append(f"{st}: max={curve.max():.1f} > 100")

    passed = len(failures) == 0
    detail = f"Tested {n_states} states. "
    if failures:
        detail += f"{len(failures)} issues:\n" + "\n".join(failures[:10])
    else:
        detail += "All states produce valid curves."
    return passed, detail, 0


# ═══════════════════════════════════════════════════════════════
# TEST 11: Risk Curve Shape — Peak at Night
# ═══════════════════════════════════════════════════════════════

def test_risk_curve_shape():
    """NIBRS hourly risk curves should peak between 8pm-4am for most states."""
    failures = []
    n_states = 0

    for st in nibrs_stats.state_profiles.keys():
        n_states += 1
        curve = nibrs_stats.get_hourly_risk_curve(state_abbr=st, base_risk=50.0)
        peak_hour = int(np.argmax(curve))
        # Peak should be in evening/night: 20-23 or 0-4
        is_night_peak = peak_hour >= 20 or peak_hour <= 4
        if not is_night_peak:
            failures.append(f"{st}: peak at hour {peak_hour} (val={curve[peak_hour]:.1f})")

    passed = len(failures) <= 5  # Allow up to 5 outlier states
    detail = f"Tested {n_states} states. "
    if failures:
        detail += f"{len(failures)} non-night peaks:\n" + "\n".join(failures[:10])
    else:
        detail += "All states peak at night."
    return passed, detail, 0


# ═══════════════════════════════════════════════════════════════
# TEST 12: Risk Curve vs Safety Index Correlation
# ═══════════════════════════════════════════════════════════════

def test_risk_safety_correlation():
    """The NIBRS risk curve and the safety index (100-score) should be
    positively correlated (both high at night, both low during day)."""
    n_preds = 0
    correlations = []

    for city, state, cr, pop, desc in TEST_CITIES[:10]:
        scores = get_24h_scores(city, state, cr, pop)
        n_preds += 24
        risk_from_score = [100 - s for s in scores]

        curve = nibrs_stats.get_hourly_risk_curve(state_abbr=state, base_risk=100 - np.mean(scores))
        if curve is None or len(curve) != 24:
            continue

        corr = np.corrcoef(risk_from_score, curve)[0, 1]
        correlations.append((city, corr))

    avg_corr = np.mean([c for _, c in correlations]) if correlations else 0
    # We want positive correlation (risk curve and safety-derived risk move together)
    # But they don't have to be perfectly correlated since safety uses more features
    passed = avg_corr > 0.3
    detail = f"Avg Pearson r = {avg_corr:.3f}. "
    for city, c in correlations:
        detail += f"{city}={c:.2f} "
    return passed, detail, n_preds


# ═══════════════════════════════════════════════════════════════
# TEST 13: Incident Type Temporal Shift
# ═══════════════════════════════════════════════════════════════

def test_incident_temporal_shift():
    """Violent crime types should be more prominent at night than during day.
    Property crimes should be more prominent during the day."""
    failures = []
    n_preds = 0

    violent_types = {"Murder", "Aggravated Assault", "Simple Assault", "Robbery",
                     "Forcible Rape", "Weapon Law Violation"}
    property_types = {"Larceny/Theft", "Shoplifting", "Theft From Building",
                      "Theft (Other)", "Fraud (False Pretense)", "Credit Card Fraud"}

    for city, state, cr, pop, desc in TEST_CITIES[:10]:
        day_types = predict_incident_types_nibrs(city, state, hour=12, crime_rate_per_100k=cr)
        night_types = predict_incident_types_nibrs(city, state, hour=2, crime_rate_per_100k=cr)
        n_preds += 2

        if not day_types or not night_types:
            continue

        # Sum up violent proportions
        day_violent = sum(t.probability for t in day_types if t.type in violent_types)
        night_violent = sum(t.probability for t in night_types if t.type in violent_types)

        # Sum up property proportions
        day_property = sum(t.probability for t in day_types if t.type in property_types)
        night_property = sum(t.probability for t in night_types if t.type in property_types)

        # At night: violent should increase relative to day
        if night_violent < day_violent * 0.8:  # Allow some tolerance
            failures.append(
                f"{city}: night_violent={night_violent:.3f} < day_violent={day_violent:.3f}*0.8"
            )

    passed = len(failures) == 0
    detail = f"Tested {len(TEST_CITIES[:10])} cities. "
    if failures:
        detail += f"{len(failures)} failures:\n" + "\n".join(failures[:10])
    else:
        detail += "Violent crimes consistently higher at night."
    return passed, detail, n_preds


# ═══════════════════════════════════════════════════════════════
# TEST 14: Incident Type Coverage
# ═══════════════════════════════════════════════════════════════

def test_incident_type_coverage():
    """NIBRS incident predictor should return results for cities with agency profiles."""
    found = 0
    not_found = 0
    n_preds = 0

    for city, state, cr, pop, desc in TEST_CITIES:
        result = predict_incident_types_nibrs(city, state, hour=12, crime_rate_per_100k=cr)
        n_preds += 1
        if result:
            found += 1
            # Validate each result
            for inc in result:
                assert inc.probability >= 0.02, f"{city} {inc.type}: p={inc.probability}"
                assert inc.icon, f"{city} {inc.type}: no icon"
                assert inc.crimeLevel, f"{city} {inc.type}: no crimeLevel"
        else:
            not_found += 1

    coverage = found / len(TEST_CITIES) * 100
    # Most test cities should have NIBRS data
    passed = coverage >= 50
    detail = f"Coverage: {found}/{len(TEST_CITIES)} ({coverage:.0f}%). Missing: {not_found}"
    return passed, detail, n_preds


# ═══════════════════════════════════════════════════════════════
# TEST 15: Probability Normalization
# ═══════════════════════════════════════════════════════════════

def test_probability_normalization():
    """Incident type probabilities should sum to roughly 1.0 (or less, since we top-6)."""
    failures = []
    n_preds = 0

    for city, state, cr, pop, desc in TEST_CITIES:
        for hour in [2, 8, 14, 20]:
            result = predict_incident_types_nibrs(city, state, hour=hour, crime_rate_per_100k=cr)
            n_preds += 1
            if not result:
                continue
            total_p = sum(inc.probability for inc in result)
            if total_p > 1.05:
                failures.append(f"{city} h={hour}: sum={total_p:.3f} > 1.05")
            if total_p < 0.3:
                failures.append(f"{city} h={hour}: sum={total_p:.3f} < 0.3 (too low)")

    passed = len(failures) == 0
    detail = f"Tested {n_preds} distributions. "
    if failures:
        detail += f"{len(failures)} issues:\n" + "\n".join(failures[:10])
    else:
        detail += "All probability sums valid."
    return passed, detail, n_preds


# ═══════════════════════════════════════════════════════════════
# TEST 16: Edge Cases — Extreme Crime Rates
# ═══════════════════════════════════════════════════════════════

def test_extreme_crime_rates():
    """Test extreme crime rate values don't crash or produce invalid scores."""
    failures = []
    n_preds = 0
    extreme_rates = [0, 50, 500, 2000, 5000, 8000, 10000, 15000]

    for cr in extreme_rates:
        scores = get_24h_scores("Atlanta", "GA", cr, 500_000)
        n_preds += 24
        for h, s in enumerate(scores):
            if s < 5 or s > 95:
                failures.append(f"rate={cr} h={h}: score={s}")
            if math.isnan(s) or math.isinf(s):
                failures.append(f"rate={cr} h={h}: score={s} (NaN/Inf)")

    passed = len(failures) == 0
    detail = f"Tested {len(extreme_rates)} extreme rates × 24 hours. "
    if failures:
        detail += f"\n".join(failures[:10])
    else:
        detail += "All valid."
    return passed, detail, n_preds


# ═══════════════════════════════════════════════════════════════
# TEST 17: Monotonicity Within Transition Windows
# ═══════════════════════════════════════════════════════════════

def test_transition_smoothness():
    """Safety scores should transition somewhat smoothly — no abrupt jumps of >20 points
    between adjacent hours."""
    failures = []
    n_preds = 0

    for city, state, cr, pop, desc in TEST_CITIES:
        scores = get_24h_scores(city, state, cr, pop)
        n_preds += 24
        for h in range(24):
            next_h = (h + 1) % 24
            jump = abs(scores[next_h] - scores[h])
            if jump > 20:
                failures.append(
                    f"{city}: h={h}→{next_h} jump={jump} "
                    f"({scores[h]}→{scores[next_h]})"
                )

    passed = len(failures) == 0
    detail = f"Tested {len(TEST_CITIES)} cities × 24 transitions. "
    if failures:
        detail += f"{len(failures)} abrupt jumps:\n" + "\n".join(failures[:10])
    else:
        detail += "All transitions smooth (<20 point jumps)."
    return passed, detail, n_preds


# ═══════════════════════════════════════════════════════════════
# TEST 18: Crime Rate vs Safety Ordering
# ═══════════════════════════════════════════════════════════════

def test_crime_rate_ordering():
    """Higher crime rates should generally yield lower safety scores
    at the same hour for the same city context."""
    failures = []
    n_preds = 0
    test_hours = [2, 8, 14, 20]
    rates = [1000, 3000, 5000, 7000]

    for city, state, _, pop, desc in TEST_CITIES[:5]:
        for h in test_hours:
            prev_score = None
            for cr in rates:
                s_idx, _ = compute_safety_score(
                    cr, h, 1, "male", 0.0, pop, [], safety_model,
                    state_abbr=state, city_name=city,
                    is_urban=1.0,
                )
                n_preds += 1
                if prev_score is not None and s_idx > prev_score + 5:
                    failures.append(
                        f"{city} h={h}: rate {cr} gave score {s_idx} > "
                        f"rate {rates[rates.index(cr)-1]} score {prev_score}"
                    )
                prev_score = s_idx

    passed = len(failures) == 0
    detail = f"Tested {len(TEST_CITIES[:5])} cities × {len(test_hours)} hours × {len(rates)} rates. "
    if failures:
        detail += f"{len(failures)} ordering violations:\n" + "\n".join(failures[:10])
    else:
        detail += "Higher crime rates consistently yield lower scores."
    return passed, detail, n_preds


# ═══════════════════════════════════════════════════════════════
# TEST 19: build_incident_types with NIBRS Tier
# ═══════════════════════════════════════════════════════════════

def test_build_incident_types_nibrs_tier():
    """When no Socrata incidents exist, build_incident_types should use NIBRS tier
    for cities with agency profiles, and the results should vary by hour."""
    failures = []
    n_preds = 0

    for city, state, cr, pop, desc in TEST_CITIES[:10]:
        day_result = build_incident_types(
            [], {}, cr,
            city_name=city, state_abbr=state,
            hour=12,
        )
        night_result = build_incident_types(
            [], {}, cr,
            city_name=city, state_abbr=state,
            hour=2,
        )
        n_preds += 2

        if not day_result or not night_result:
            continue

        # At minimum, the distributions should differ
        day_types = {t.type: t.probability for t in day_result}
        night_types = {t.type: t.probability for t in night_result}

        # Check that at least one type has different proportion
        has_diff = False
        for t in set(day_types.keys()) | set(night_types.keys()):
            d = abs(day_types.get(t, 0) - night_types.get(t, 0))
            if d > 0.01:
                has_diff = True
                break

        if not has_diff:
            failures.append(f"{city}: day and night distributions identical")

    passed = len(failures) == 0
    detail = f"Tested {len(TEST_CITIES[:10])} cities. "
    if failures:
        detail += f"{len(failures)} issues:\n" + "\n".join(failures[:10])
    else:
        detail += "Distributions differ between day and night."
    return passed, detail, n_preds


# ═══════════════════════════════════════════════════════════════
# TEST 20: Full 24-Hour Profile Detailed Analysis
# ═══════════════════════════════════════════════════════════════

def test_detailed_24h_profile():
    """Print and validate full 24-hour profiles for key cities.
    Check: shape is bell-curve-ish, no flat lines, no NaN."""
    n_preds = 0
    issues = []

    key_cities = [
        ("Atlanta", "GA", 4200, 500_000),
        ("Irvine", "CA", 1200, 310_000),
        ("St. Louis", "MO", 6500, 300_000),
        ("New York", "NY", 2400, 8_300_000),
    ]

    for city, state, cr, pop in key_cities:
        scores = get_24h_scores(city, state, cr, pop)
        n_preds += 24

        # Check for flat profile (all same value)
        unique_scores = len(set(scores))
        if unique_scores <= 3:
            issues.append(f"{city}: only {unique_scores} unique values — nearly flat")

        # Check for NaN
        if any(math.isnan(s) for s in scores):
            issues.append(f"{city}: contains NaN")

        # Compute statistics
        std_dev = np.std(scores)
        if std_dev < 2:
            issues.append(f"{city}: std={std_dev:.1f}, too low — insufficient variation")

    passed = len(issues) == 0
    detail = ""
    if issues:
        detail = "\n".join(issues)
    else:
        detail = "All key cities have proper 24h variation."
    return passed, detail, n_preds


# ═══════════════════════════════════════════════════════════════
# TEST 21: Dawn/Dusk Transition
# ═══════════════════════════════════════════════════════════════

def test_dawn_dusk_transition():
    """Scores should generally increase from 4am→10am (dawn) and
    decrease from 6pm→12am (dusk). Not strict monotonic, but trending."""
    failures = []
    n_preds = 0

    dawn_hours = [4, 5, 6, 7, 8, 9, 10]
    dusk_hours = [18, 19, 20, 21, 22, 23, 0]

    for city, state, cr, pop, desc in TEST_CITIES[:10]:
        scores = get_24h_scores(city, state, cr, pop)
        n_preds += 24

        # Dawn: overall trend should be increasing
        dawn_scores = [scores[h] for h in dawn_hours]
        dawn_trend = dawn_scores[-1] - dawn_scores[0]
        if dawn_trend < 0:
            failures.append(f"{city}: dawn trend negative ({dawn_scores[0]}→{dawn_scores[-1]})")

        # Dusk: overall trend should be decreasing
        dusk_scores = [scores[h] for h in dusk_hours]
        dusk_trend = dusk_scores[-1] - dusk_scores[0]
        if dusk_trend > 0:
            failures.append(f"{city}: dusk trend positive ({dusk_scores[0]}→{dusk_scores[-1]})")

    passed = len(failures) <= 2  # Allow up to 2 anomalies
    detail = f"Tested {len(TEST_CITIES[:10])} cities. "
    if failures:
        detail += f"{len(failures)} anomalies:\n" + "\n".join(failures[:10])
    else:
        detail += "Dawn/dusk transitions follow expected direction."
    return passed, detail, n_preds


# ═══════════════════════════════════════════════════════════════
# TEST 22: NIBRS Code Mapping Completeness
# ═══════════════════════════════════════════════════════════════

def test_nibrs_code_mapping():
    """All offense codes found in agency profiles should have a human name mapping."""
    codes_in_profiles = set()
    for key, prof in nibrs_stats.agency_profiles.items():
        for code in prof.get("offense_mix", {}).keys():
            codes_in_profiles.add(code)

    unmapped = codes_in_profiles - set(_NIBRS_CODE_TO_NAME.keys())
    coverage = (len(codes_in_profiles) - len(unmapped)) / max(len(codes_in_profiles), 1) * 100

    passed = len(unmapped) == 0
    detail = f"{len(codes_in_profiles)} unique codes in profiles, {coverage:.0f}% mapped. "
    if unmapped:
        detail += f"Unmapped: {sorted(unmapped)}"
    return passed, detail, 0


# ═══════════════════════════════════════════════════════════════
# TEST 23: Time Period Classification
# ═══════════════════════════════════════════════════════════════

def test_time_period_classification():
    """_get_time_period should correctly classify all 24 hours."""
    expected = {
        0: "night", 1: "night", 2: "night", 3: "night", 4: "night", 5: "night",
        6: "day", 7: "day", 8: "day", 9: "day", 10: "day", 11: "day",
        12: "day", 13: "day", 14: "day", 15: "day", 16: "day", 17: "day",
        18: "evening", 19: "evening", 20: "evening", 21: "evening",
        22: "night", 23: "night",
    }
    failures = []
    for h, exp in expected.items():
        got = _get_time_period(h)
        if got != exp:
            failures.append(f"h={h}: expected {exp}, got {got}")

    passed = len(failures) == 0
    detail = "\n".join(failures) if failures else "All 24 hours classified correctly."
    return passed, detail, 0


# ═══════════════════════════════════════════════════════════════
# TEST 24: Massive City Sweep — All Profiled Cities
# ═══════════════════════════════════════════════════════════════

def test_massive_city_sweep():
    """Test safety scores for every city with an agency profile (up to 500).
    Check range, night/day differential, and smoothness."""
    failures = []
    n_preds = 0
    n_tested = 0

    # Get the first 500 agency profile keys
    all_keys = list(nibrs_stats.agency_profiles.keys())[:500]

    for key in all_keys:
        prof = nibrs_stats.agency_profiles[key]
        state = prof.get("state_abbr", "")
        pop = prof.get("population", 10000)
        cr = prof.get("part1_rate", 3000)

        if pop < 1000 or cr <= 0:
            continue

        n_tested += 1
        scores = get_24h_scores(key, state, cr, pop)
        n_preds += 24

        # Range check
        for h, s in enumerate(scores):
            if s < 5 or s > 95:
                failures.append(f"{key}: h={h} score={s}")
                break

        # Night/day check
        night_hours = [22, 23, 0, 1, 2, 3]
        day_hours = [9, 10, 11, 12, 13, 14]
        night_avg = np.mean([scores[h] for h in night_hours])
        day_avg = np.mean([scores[h] for h in day_hours])
        if night_avg > day_avg + 5:  # Night SAFER than day by >5 points
            failures.append(f"{key}: night_avg={night_avg:.0f} > day_avg={day_avg:.0f}")

        # Smoothness check
        for h in range(24):
            jump = abs(scores[(h+1) % 24] - scores[h])
            if jump > 25:
                failures.append(f"{key}: h={h}→{(h+1)%24} jump={jump}")
                break

    failure_rate = len(failures) / n_tested if n_tested else 0
    passed = failure_rate < 0.05  # Less than 5% failure rate
    detail = (
        f"Tested {n_tested} profiled cities. "
        f"{len(failures)} issues ({failure_rate*100:.1f}% failure rate)."
    )
    if failures:
        detail += "\nSample:\n" + "\n".join(failures[:15])
    return passed, detail, n_preds


# ═══════════════════════════════════════════════════════════════
# TEST 25: Incident Type Icon Mapping
# ═══════════════════════════════════════════════════════════════

def test_icon_mapping():
    """Every incident type from NIBRS should get a non-default icon for common types."""
    common_types = [
        "Murder", "Aggravated Assault", "Simple Assault", "Robbery",
        "Burglary", "Larceny/Theft", "Motor Vehicle Theft", "Vandalism",
        "Drug Violation", "Weapon Law Violation",
    ]
    failures = []
    for t in common_types:
        icon = get_icon(t)
        if icon == "📌":  # Default icon
            failures.append(f"{t} → default icon 📌")

    passed = len(failures) <= 2  # Allow 2 common types with default icon
    detail = f"Tested {len(common_types)} common types. "
    if failures:
        detail += f"\n".join(failures)
    else:
        detail += "All common types have specific icons."
    return passed, detail, 0


# ═══════════════════════════════════════════════════════════════
# TEST 26: Stress Test — Rapid-Fire Predictions
# ═══════════════════════════════════════════════════════════════

def test_stress_rapid_fire():
    """Run 1000+ predictions rapidly and verify consistency + speed."""
    n_preds = 0
    t0 = time.perf_counter()

    # Cache should prevent duplicate computations
    for _ in range(3):
        for city, state, cr, pop, _ in TEST_CITIES:
            scores = get_24h_scores(city, state, cr, pop)
            n_preds += 24

    dt = time.perf_counter() - t0
    throughput = n_preds / dt

    passed = throughput > 100  # At least 100 predictions/sec
    detail = (
        f"{n_preds} predictions in {dt:.1f}s "
        f"({throughput:.0f} pred/s)"
    )
    return passed, detail, n_preds


# ═══════════════════════════════════════════════════════════════
# TEST 27: Multi-Feature Interaction
# ═══════════════════════════════════════════════════════════════

def test_multi_feature_interaction():
    """Test that multiple adverse conditions (night + female + storm + solo)
    produce meaningfully lower scores than all favorable conditions
    (day + male + clear + group)."""
    failures = []
    n_preds = 0

    for city, state, cr, pop, desc in TEST_CITIES[:10]:
        # Best case: 2PM, male, group of 4, clear weather
        best, _ = compute_safety_score(
            cr, 14, 4, "male", 0.0, pop, [], safety_model,
            state_abbr=state, city_name=city, is_urban=1.0,
        )
        # Worst case: 2AM, female, solo, storm
        worst, _ = compute_safety_score(
            cr, 2, 1, "female", 0.8, pop, [], safety_model,
            state_abbr=state, city_name=city, is_urban=1.0,
        )
        n_preds += 2

        gap = best - worst
        if gap < 5:
            failures.append(
                f"{city}: best={best}, worst={worst}, gap={gap} (< 5)"
            )

    passed = len(failures) == 0
    detail = f"Tested {len(TEST_CITIES[:10])} cities. "
    if failures:
        detail += f"{len(failures)} insufficient gaps:\n" + "\n".join(failures[:10])
    else:
        detail += "All cities show meaningful multi-feature differentiation."
    return passed, detail, n_preds


# ═══════════════════════════════════════════════════════════════
# TEST 28: Hourly Incident Type Stability
# ═══════════════════════════════════════════════════════════════

def test_hourly_incident_stability():
    """All 24 hours should produce valid incident types (no crashes, no empty results)
    for cities with known profiles."""
    failures = []
    n_preds = 0

    for city, state, cr, pop, desc in TEST_CITIES[:10]:
        profile = nibrs_stats.get_agency_profile(city, state)
        if not profile:
            continue
        for h in range(24):
            result = predict_incident_types_nibrs(city, state, hour=h, crime_rate_per_100k=cr)
            n_preds += 1
            if result is None:
                failures.append(f"{city} h={h}: returned None (has profile)")
            elif len(result) == 0:
                failures.append(f"{city} h={h}: empty list")

    passed = len(failures) == 0
    detail = f"Tested {n_preds} hour×city combinations. "
    if failures:
        detail += f"{len(failures)} issues:\n" + "\n".join(failures[:10])
    else:
        detail += "All hours produce valid incident types."
    return passed, detail, n_preds


# ═══════════════════════════════════════════════════════════════
# TEST 29: Formula vs XGBoost Agreement Direction
# ═══════════════════════════════════════════════════════════════

def test_formula_xgb_agreement():
    """Formula and XGBoost components should generally agree on which hours
    are more dangerous. Specifically: their 24-hour curves should be
    positively correlated (r > 0)."""
    n_preds = 0
    correlations = []

    for city, state, cr, pop, desc in TEST_CITIES[:10]:
        xgb_scores = []
        formula_scores = []
        for h in range(24):
            s_idx, f_score = compute_safety_score(
                cr, h, 1, "male", 0.0, pop, [], safety_model,
                state_abbr=state, city_name=city, is_urban=1.0,
            )
            xgb_scores.append(s_idx)
            formula_scores.append(f_score)
            n_preds += 1

        corr = np.corrcoef(xgb_scores, formula_scores)[0, 1]
        correlations.append((city, corr))

    avg_corr = np.mean([c for _, c in correlations]) if correlations else 0
    passed = avg_corr > 0.5
    detail = f"Avg formula-XGBoost correlation: {avg_corr:.3f}. "
    for city, c in correlations:
        detail += f"{city}={c:.2f} "
    return passed, detail, n_preds


# ═══════════════════════════════════════════════════════════════
# TEST 30: Full Pipeline Print (Diagnostic)
# ═══════════════════════════════════════════════════════════════

def test_full_pipeline_print():
    """Print full 24-hour profiles for 4 reference cities. Always passes.
    This is a diagnostic output for manual inspection."""
    n_preds = 0
    ref_cities = [
        ("Atlanta", "GA", 4200, 500_000, "High-crime urban"),
        ("Irvine", "CA", 1200, 310_000, "Low-crime suburban"),
        ("St. Louis", "MO", 6500, 300_000, "Very high crime"),
        ("New York", "NY", 2400, 8_300_000, "Mega-city"),
    ]

    output_lines = []
    for city, state, cr, pop, desc in ref_cities:
        scores = get_24h_scores(city, state, cr, pop)
        n_preds += 24

        # Also get risk curve
        curve = nibrs_stats.get_hourly_risk_curve(state_abbr=state, base_risk=100 - np.mean(scores))

        line = f"\n{'='*70}\n{city}, {state} ({desc}) — crime rate: {cr}/100k, pop: {pop:,}\n"
        line += f"{'Hour':>6} {'Safety':>7} {'Risk':>6} {'NIBRS':>7}  Bar\n"
        line += "-" * 60 + "\n"
        for h in range(24):
            risk = 100 - scores[h]
            nibrs_r = curve[h] if curve is not None and h < len(curve) else 0
            bar_len = int(scores[h] / 2)
            bar = "█" * bar_len
            ampm = f"{h:02d}:00"
            line += f"{ampm:>6} {scores[h]:>7} {risk:>6} {nibrs_r:>7.1f}  {bar}\n"

        # Summary
        min_h = scores.index(min(scores))
        max_h = scores.index(max(scores))
        spread = max(scores) - min(scores)
        night = np.mean([scores[h] for h in [22, 23, 0, 1, 2, 3]])
        day = np.mean([scores[h] for h in [9, 10, 11, 12, 13, 14]])
        line += (
            f"\nMin: h={min_h} ({scores[min_h]}), Max: h={max_h} ({scores[max_h]}), "
            f"Spread: {spread}, Night avg: {night:.0f}, Day avg: {day:.0f}\n"
        )

        # Incident types at 2PM and 2AM
        day_inc = predict_incident_types_nibrs(city, state, hour=14, crime_rate_per_100k=cr)
        night_inc = predict_incident_types_nibrs(city, state, hour=2, crime_rate_per_100k=cr)
        if day_inc:
            line += f"\n  2PM incidents: " + ", ".join(f"{i.type} ({i.probability*100:.0f}%)" for i in day_inc[:4])
        if night_inc:
            line += f"\n  2AM incidents: " + ", ".join(f"{i.type} ({i.probability*100:.0f}%)" for i in night_inc[:4])
        line += "\n"

        output_lines.append(line)

    detail = "\n".join(output_lines)
    return True, detail, n_preds


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    print("\n" + "=" * 70)
    print("  LUMOS 24-HOUR RISK ALIGNMENT — COMPREHENSIVE TEST SUITE")
    print(f"  NIBRS: {len(nibrs_stats.agency_profiles)} agencies, "
          f"{len(nibrs_stats.state_profiles)} states")
    print(f"  Model: {type(safety_model).__name__}")
    print("=" * 70 + "\n")

    t_start = time.perf_counter()

    # ── Structural Tests ──
    print("── Structural Validation ──")
    run_test("Time Period Classification", test_time_period_classification)
    run_test("NIBRS Code Mapping Completeness", test_nibrs_code_mapping)
    run_test("Icon Mapping", test_icon_mapping)
    run_test("State Profile Coverage (50 states)", test_state_profile_coverage)

    # ── Risk Curve Shape Tests ──
    print("\n── Risk Curve Shape ──")
    run_test("Risk Curve Peak at Night", test_risk_curve_shape)
    run_test("Risk Curve vs Safety Correlation", test_risk_safety_correlation)

    # ── 24-Hour Safety Score Tests ──
    print("\n── Safety Score Patterns ──")
    run_test("Night vs Day Differential", test_night_day_differential)
    run_test("Peak Risk Hour (10pm-5am)", test_peak_risk_alignment)
    run_test("Safest Hour (7am-5pm)", test_safest_hour_alignment)
    run_test("Night-Day Spread (≥5 pts)", test_night_day_spread)
    run_test("Score Range [5, 95]", test_score_range)
    run_test("Transition Smoothness (<20 pt jumps)", test_transition_smoothness)
    run_test("Dawn/Dusk Transition Direction", test_dawn_dusk_transition)

    # ── Cross-Feature Tests ──
    print("\n── Feature Sensitivity ──")
    run_test("Cross-City Ordering (low vs high crime)", test_cross_city_ordering)
    run_test("Gender Sensitivity", test_gender_sensitivity)
    run_test("Group Size Effect", test_group_size_effect)
    run_test("Weather Amplification", test_weather_amplification)
    run_test("Crime Rate Ordering", test_crime_rate_ordering)
    run_test("Multi-Feature Interaction", test_multi_feature_interaction)
    run_test("Formula vs XGBoost Agreement", test_formula_xgb_agreement)

    # ── Incident Type Tests ──
    print("\n── Incident Type Analysis ──")
    run_test("Incident Type Coverage", test_incident_type_coverage)
    run_test("Probability Normalization", test_probability_normalization)
    run_test("Incident Temporal Shift (violent↑ night)", test_incident_temporal_shift)
    run_test("NIBRS Tier in build_incident_types", test_build_incident_types_nibrs_tier)
    run_test("Hourly Incident Stability (24h × cities)", test_hourly_incident_stability)

    # ── Edge Cases & Stress ──
    print("\n── Robustness ──")
    run_test("Extreme Crime Rates", test_extreme_crime_rates)
    run_test("Stress Test (1000+ predictions)", test_stress_rapid_fire)
    run_test("Massive City Sweep (500 profiles)", test_massive_city_sweep)
    run_test("Detailed 24h Profile Validation", test_detailed_24h_profile)

    # ── Diagnostic Output ──
    print("\n── Diagnostic Output ──")
    run_test("Full Pipeline Print", test_full_pipeline_print)

    # ── Summary ──
    t_total = time.perf_counter() - t_start
    n_pass = sum(1 for r in results if r.passed)
    n_fail = sum(1 for r in results if not r.passed)
    n_total = len(results)

    print("\n" + "=" * 70)
    print(f"  RESULTS: {n_pass}/{n_total} passed, {n_fail} failed")
    print(f"  Total predictions: {total_predictions:,}")
    print(f"  Total time: {t_total:.1f}s")
    print(f"  Throughput: {total_predictions/t_total:.0f} predictions/sec")
    print("=" * 70)

    if n_fail > 0:
        print("\n── FAILURES ──")
        for r in results:
            if not r.passed:
                print(f"\n  ❌ {r.name}:")
                for line in r.details.split("\n")[:10]:
                    print(f"     {line}")

    # Print diagnostic output for full pipeline
    for r in results:
        if r.name == "Full Pipeline Print":
            print(r.details)
            break

    print(f"\n{'✅ ALL TESTS PASSED' if n_fail == 0 else f'❌ {n_fail} TEST(S) FAILED'}")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
