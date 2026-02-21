"""Lumos Backend — Area Sentiment via GDELT News + Incident Pattern Analysis.

GDELT DOC 2.0 API is free and requires no API key.
Incident pattern analysis uses already-fetched Socrata/NWS live incidents.
"""

import logging
from collections import Counter
from datetime import datetime

import httpx

logger = logging.getLogger("lumos.sentiment")

_sentiment_client = httpx.AsyncClient(timeout=10.0)

GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"


async def fetch_gdelt_news(city_name: str, state_abbr: str = "") -> list[dict]:
    """Fetch recent safety-related news articles for a location via GDELT DOC 2.0.

    Returns list of dicts: {title, url, tone, seendate}.
    GDELT tone: negative = concerning, positive = reassuring.
    """
    if not city_name or len(city_name.strip()) < 2:
        return []

    location_query = city_name.split(",")[0].strip()
    if state_abbr:
        location_query = f"{location_query} {state_abbr}"

    query = f'"{location_query}" (crime OR safety OR police OR shooting OR robbery OR theft OR assault)'

    try:
        r = await _sentiment_client.get(GDELT_DOC_API, params={
            "query": query,
            "mode": "ArtList",
            "maxrecords": "15",
            "format": "json",
            "sort": "DateDesc",
            "timespan": "7d",
        })
        if r.status_code != 200:
            logger.warning(f"GDELT returned {r.status_code} for {location_query}")
            return []

        data = r.json()
        articles = data.get("articles", [])

        results = []
        for art in articles[:15]:
            results.append({
                "title": art.get("title", "").strip(),
                "url": art.get("url", ""),
                "tone": art.get("tone", 0.0),
                "seendate": art.get("seendate", ""),
                "domain": art.get("domain", ""),
            })

        logger.info(f"GDELT: {len(results)} articles for {location_query}")
        return results

    except Exception as e:
        logger.warning(f"GDELT fetch failed for {location_query}: {e}")
        return []


def analyze_incident_patterns(live_incidents: list[dict]) -> dict:
    """Analyze already-fetched live incidents to produce a pattern summary.

    Returns dict with:
      - type_distribution: {type: count}
      - dominant_type: str
      - dominant_pct: float
      - time_pattern: str (e.g. "Most incidents between 8 PM - 2 AM")
      - total_count: int
      - summary: str (human-readable)
    """
    if not live_incidents:
        return {
            "type_distribution": {},
            "dominant_type": "",
            "dominant_pct": 0.0,
            "time_pattern": "",
            "total_count": 0,
            "summary": "No recent incidents reported nearby.",
        }

    type_counts = Counter()
    hour_counts = Counter()

    for inc in live_incidents:
        inc_type = inc.get("type", "Unknown")
        type_counts[inc_type] += 1

        date_str = inc.get("date", "")
        if date_str:
            try:
                if "T" in str(date_str):
                    dt = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
                    hour_counts[dt.hour] += 1
            except (ValueError, TypeError):
                pass

    total = sum(type_counts.values())
    dominant_type, dominant_count = type_counts.most_common(1)[0] if type_counts else ("Unknown", 0)
    dominant_pct = (dominant_count / total * 100) if total > 0 else 0

    # Determine time-of-day pattern
    time_pattern = ""
    if hour_counts:
        night_count = sum(hour_counts[h] for h in range(20, 24)) + sum(hour_counts[h] for h in range(0, 6))
        day_count = sum(hour_counts[h] for h in range(6, 20))
        if night_count > day_count * 1.5:
            time_pattern = "Concentrated between 8 PM and 6 AM"
        elif day_count > night_count * 1.5:
            time_pattern = "Concentrated during daytime hours (6 AM - 8 PM)"
        else:
            time_pattern = "Spread throughout the day"

    # Build summary string
    top_3 = type_counts.most_common(3)
    type_parts = [f"{t} ({c} incidents)" for t, c in top_3]
    summary_parts = []
    if dominant_pct >= 40:
        summary_parts.append(f"{dominant_type} dominant ({dominant_pct:.0f}%): {', '.join(type_parts)}")
    else:
        summary_parts.append(f"Mixed incident types: {', '.join(type_parts)}")
    if time_pattern:
        summary_parts.append(time_pattern)

    return {
        "type_distribution": dict(type_counts),
        "dominant_type": dominant_type,
        "dominant_pct": dominant_pct,
        "time_pattern": time_pattern,
        "total_count": total,
        "summary": ". ".join(summary_parts) + ".",
    }


def build_sentiment_summary(
    gdelt_results: list[dict],
    incident_analysis: dict,
    city_name: str = "",
) -> str:
    """Combine GDELT news sentiment + incident patterns into a concise summary string."""
    parts = []

    # News sentiment
    if gdelt_results:
        tones = [a.get("tone", 0.0) for a in gdelt_results if isinstance(a.get("tone"), (int, float))]
        avg_tone = sum(tones) / len(tones) if tones else 0.0

        negative_articles = [a for a in gdelt_results if isinstance(a.get("tone"), (int, float)) and a["tone"] < -2]
        positive_articles = [a for a in gdelt_results if isinstance(a.get("tone"), (int, float)) and a["tone"] > 2]

        if negative_articles:
            headlines = [a["title"][:80] for a in negative_articles[:3] if a.get("title")]
            if headlines:
                parts.append(f"Recent news ({len(gdelt_results)} articles, avg tone {avg_tone:+.1f}): "
                           f"concerning coverage includes: {'; '.join(headlines)}")
            else:
                parts.append(f"Recent news: {len(negative_articles)} articles with negative safety tone")
        elif positive_articles:
            parts.append(f"Recent news tone is generally positive ({len(gdelt_results)} articles, avg {avg_tone:+.1f})")
        elif gdelt_results:
            parts.append(f"Recent news: {len(gdelt_results)} articles, neutral tone (avg {avg_tone:+.1f})")
    else:
        parts.append("Limited local news coverage for this area")

    # Incident patterns
    inc_summary = incident_analysis.get("summary", "")
    if inc_summary and incident_analysis.get("total_count", 0) > 0:
        parts.append(f"Incident pattern: {inc_summary}")

    return " | ".join(parts) if parts else ""
