"""
ml/enrichment.py

Phase 3: Hyper-Granular Data Enrichment.

Adds rich contextual features to raw transactions before they enter the ML pipeline:
  - Temporal:  hour_of_day, day_of_week, is_weekend, is_payday_week
  - Merchant:  merchant_slug (normalised), recurrence_score
  - Spatial:   geo_bucket (if lat/lon provided)
  - Behavioural: impulse_score (unplanned purchases vs. recurring)

These enriched fields feed into ml/features.py for higher-accuracy predictions
and into the RAG indexing layer for richer semantic search.
"""
from __future__ import annotations

import re
import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

log = logging.getLogger("enrichment")

#  Merchant normalisation  #

# Map of common merchant keywords to clean slugs
_MERCHANT_MAP = {
    r"highland|highlands coffee": "highland_coffee",
    r"grab(food|taxi|bike|car)?": "grab",
    r"gojek|go-jek|gofood": "gojek",
    r"shopee": "shopee",
    r"lazada": "lazada",
    r"netflix": "netflix",
    r"spotify": "spotify",
    r"youtube premium": "youtube_premium",
    r"momo|moma|momopay": "momo",
    r"7[-\s]?eleven|711": "seven_eleven",
    r"circle ?k": "circle_k",
    r"family mart|familymart": "family_mart",
    r"starbucks": "starbucks",
    r"kfc": "kfc",
    r"mcdonald|mcdonalds|mcd": "mcdonalds",
    r"jollibee": "jollibee",
    r"vinmart|winmart": "vinmart",
    r"lotte mart": "lotte_mart",
    r"big c": "big_c",
}


def _normalise_merchant(raw: str) -> str:
    """Normalise a raw merchant name or note to a clean slug."""
    if not raw:
        return "unknown"
    cleaned = raw.strip().lower()
    for pattern, slug in _MERCHANT_MAP.items():
        if re.search(pattern, cleaned):
            return slug
    # Fallback: slugify the first 3 words
    words = re.sub(r"[^a-z0-9\s]", "", cleaned).split()
    return "_".join(words[:3]) or "unknown"


#  Geo bucket  #

def _geo_bucket(lat: Optional[float], lon: Optional[float]) -> str:
    """
    Assign a coarse geography label from coordinates.
    In production this would call a reverse-geocoding service or PostGIS.
    For now, uses a simple bounding-box heuristic (configured for Hanoi / HCMC).
    """
    if lat is None or lon is None:
        return "unknown"
    # Rough bounding boxes for major ASEAN zones
    zones = {
        "ho_chi_minh_cbd": (10.762, 10.790, 106.685, 106.710),
        "hanoi_cbd":        (21.020, 21.040, 105.840, 105.860),
        "bangkok_cbd":      (13.720, 13.760, 100.500, 100.560),
        "manila_cbd":       (14.575, 14.600, 120.980, 121.010),
        "jakarta_cbd":      (-6.215, -6.185, 106.815, 106.845),
        "singapore_cbd":    (1.270, 1.300, 103.840, 103.870),
    }
    for zone, (min_lat, max_lat, min_lon, max_lon) in zones.items():
        if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
            return zone
    return "other"


#  Recurrence detection  #

def _compute_recurrence_scores(tx_list: list[dict]) -> dict[str, float]:
    """
    For each merchant slug, compute how often it appears per week.
    Returns a dict mapping merchant_slug -> recurrence_score (0.0–1.0).
    """
    if not tx_list:
        return {}
    counts: Counter = Counter()
    weeks: set = set()
    for tx in tx_list:
        slug = tx.get("merchant_slug", "unknown")
        counts[slug] += 1
        try:
            dt = pd.to_datetime(tx.get("timestamp", ""), utc=True)
            week_key = f"{dt.year}-W{dt.isocalendar()[1]}"
            weeks.add(week_key)
        except Exception:
            pass

    num_weeks = max(len(weeks), 1)
    max_count = max(counts.values(), default=1)
    return {slug: min(count / (num_weeks * max_count), 1.0) for slug, count in counts.items()}


#  Main enrichment function  #

def enrich_transaction(tx: dict, recurrence_scores: Optional[dict] = None) -> dict:
    """
    Enrich a single transaction with temporal, merchant, spatial, and behavioural features.

    Args:
        tx:                 Raw transaction dict.
        recurrence_scores:  Pre-computed recurrence scores dict (optional, for performance).

    Returns:
        A new dict containing all original fields plus enriched fields.
    """
    enriched = dict(tx)  # Copy, never mutate original

    #  Temporal features 
    try:
        dt = pd.to_datetime(tx.get("timestamp", ""), utc=True)
        enriched["hour_of_day"]    = dt.hour
        enriched["day_of_week"]    = dt.day_of_week  # 0=Mon, 6=Sun
        enriched["is_weekend"]     = int(dt.day_of_week >= 5)
        enriched["day_of_month"]   = dt.day
        enriched["is_payday_week"] = int(dt.day <= 5 or dt.day >= 25)
        enriched["week_of_month"]  = (dt.day - 1) // 7 + 1
    except Exception:
        enriched.update({
            "hour_of_day": -1, "day_of_week": -1,
            "is_weekend": 0,   "day_of_month": -1,
            "is_payday_week": 0, "week_of_month": -1,
        })

    #  Merchant slug 
    raw_merchant = tx.get("merchant_name") or tx.get("note") or tx.get("category", "")
    slug = _normalise_merchant(raw_merchant)
    enriched["merchant_slug"] = slug

    #  Spatial features 
    enriched["geo_bucket"] = _geo_bucket(tx.get("latitude"), tx.get("longitude"))

    #  Recurrence score 
    rec_scores = recurrence_scores or {}
    enriched["recurrence_score"] = rec_scores.get(slug, 0.0)

    #  Impulse score: high if it's a new merchant, weekend, odd hour 
    impulse = 0.0
    if enriched["recurrence_score"] < 0.1:
        impulse += 0.5   # new / rare merchant
    if enriched["is_weekend"]:
        impulse += 0.2
    if enriched.get("hour_of_day", 0) >= 22 or enriched.get("hour_of_day", 12) <= 6:
        impulse += 0.3   # late night / early morning purchase
    enriched["impulse_score"] = min(impulse, 1.0)

    return enriched


def enrich_snapshot_transactions(snapshot: dict) -> list[dict]:
    """
    Enrich all transactions in a wallet snapshot.

    Returns a list of enriched transaction dicts, suitable for both
    ML feature engineering and RAG indexing.
    """
    raw_txs = snapshot.get("transactions", []) or []
    parsed = []
    for t in raw_txs:
        if not isinstance(t, dict):
            t = t.__dict__ if hasattr(t, "__dict__") else {}
        parsed.append(t)

    # Pre-compute recurrence across all transactions
    pre_enriched = []
    for t in parsed:
        raw_merchant = t.get("merchant_name") or t.get("note") or t.get("category", "")
        pre_enriched.append({"timestamp": t.get("timestamp"), "merchant_slug": _normalise_merchant(raw_merchant)})

    recurrence_scores = _compute_recurrence_scores(pre_enriched)

    return [enrich_transaction(t, recurrence_scores) for t in parsed]
