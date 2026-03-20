"""
ml/inference_core.py

Core prediction logic used by the API:
    predict_burn_risk_from_snapshot(snapshot: dict) -> dict

Strategy:
  1. Load trained model (burn_rate_model.pkl) if available
  2. Build feature vector using ml/features.py
  3. Get shortfall_prob from model (or deterministic math fallback)
  4. Compute projections: predicted_total_spend, month_end_balance, overshoot
  5. Identify top risky categories
  6. Return a dict consumed by app/api.py
"""
import json
import logging
from datetime import timezone
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd

from ml.features import build_inference_features, FEATURE_COLUMNS, _cat_bucket

log = logging.getLogger("inference_core")

ROOT        = Path(__file__).parent.parent
MODEL_PATH  = ROOT / "models" / "burn_rate_model.pkl"
CFG_PATH    = ROOT / "models" / "feature_config.json"

# Lazy-loaded model (loaded once at first call)
_model = None


def _load_model():
    global _model
    if _model is not None:
        return _model
    if MODEL_PATH.exists():
        try:
            _model = joblib.load(MODEL_PATH)
            log.info(f" Model loaded from {MODEL_PATH}")
        except Exception as e:
            log.warning(f"Failed to load model: {e}")
            _model = None
    else:
        log.warning(f"Model file not found at {MODEL_PATH}. Using rule-based fallback.")
    return _model


def _rule_based_shortfall_prob(
    progress: float,
    budget_used_pct: float,
    delta_spend_rate: float,
) -> float:
    """
    Simple deterministic proxy for shortfall probability when model is unavailable.
    """
    base = budget_used_pct / max(progress, 0.01)   # spend velocity vs time
    # Penalise if spending is accelerating
    accel_penalty = max(delta_spend_rate, 0) / 1_000_000
    prob = min(base - 1.0, 1.0)
    prob = max(prob + accel_penalty * 0.1, 0.0)
    return float(np.clip(prob, 0.0, 1.0))


def predict_burn_risk_from_snapshot(snapshot: dict) -> dict:
    """
    Main inference function.

    Args:
        snapshot: dict that matches PredictBurnRateRequest fields
                  (converted to dict before calling)

    Returns:
        dict with keys matching PredictBurnRateResponse (minus ai_message)
    """
    from datetime import datetime
    import calendar

    #  Parse input 
    current_date  = pd.to_datetime(snapshot.get("current_date", datetime.now(timezone.utc).date()))
    day           = current_date.day
    month         = current_date.month
    year          = current_date.year
    days_in_month = calendar.monthrange(year, month)[1]
    progress      = day / days_in_month

    # Balances
    balances   = snapshot.get("balances", {})
    if hasattr(balances, "__dict__"):
        balances = balances.__dict__
    total_balance = float(balances.get("banking", 0)) + float(balances.get("cash", 0))

    # Budget
    budget = snapshot.get("monthly_budget", {})
    if hasattr(budget, "__dict__"):
        budget = budget.__dict__
    budget_total     = float(budget.get("total", 0))
    budget_by_cat    = budget.get("by_category", {}) or {}
    if hasattr(budget_by_cat, "__dict__"):
        budget_by_cat = budget_by_cat.__dict__

    # Essential obligations
    obligations  = snapshot.get("essential_obligations", []) or []
    essential_total = sum(
        float(o.get("amount", 0) if isinstance(o, dict) else getattr(o, "amount", 0))
        for o in obligations
    )

    # Transactions (parse to standard format)
    raw_txs = snapshot.get("transactions", []) or []
    tx_rows = []
    for t in raw_txs:
        if not isinstance(t, dict):
            t = t.__dict__ if hasattr(t, "__dict__") else {}
        ts   = pd.to_datetime(t.get("timestamp", current_date), utc=True, errors="coerce")
        amt  = abs(float(t.get("amount", 0)))
        typ  = str(t.get("type", "expense")).lower()
        cat  = str(t.get("category", "Other"))
        tx_rows.append({"timestamp": ts, "amount": amt, "type": typ, "category": cat})
    tx_df = pd.DataFrame(tx_rows) if tx_rows else pd.DataFrame(
        columns=["timestamp","amount","type","category"]
    )

    # MTD (current month only)
    current_month_start = pd.Timestamp(year=year, month=month, day=1, tz="UTC")
    current_date_ts     = pd.Timestamp(current_date.date(), tz="UTC")
    if len(tx_df) > 0:
        mtd_mask = (tx_df["timestamp"] >= current_month_start) & (tx_df["timestamp"] <= current_date_ts)
        mtd = tx_df[mtd_mask]
    else:
        mtd = tx_df

    exp_mtd  = mtd[mtd["type"] == "expense"] if len(mtd) > 0 else mtd
    inc_mtd  = mtd[mtd["type"] == "income"]  if len(mtd) > 0 else mtd
    spend_mtd = float(exp_mtd["amount"].sum())
    income_mtd = float(inc_mtd["amount"].sum())

    #  Feature vector and model prediction 
    try:
        feature_df = build_inference_features(snapshot)
        model = _load_model()
        if model is not None:
            X = feature_df[FEATURE_COLUMNS].fillna(0)
            shortfall_prob = float(model.predict_proba(X)[0, 1])
            model_used = True
        else:
            raise RuntimeError("model not loaded")
    except Exception as e:
        log.warning(f"Model prediction failed ({e}), using rule-based fallback")
        avg_daily = spend_mtd / max(day, 1)
        delta = avg_daily - (float(tx_df[tx_df["type"]=="expense"]["amount"].sum()) /
                             max((current_date_ts - current_month_start).days + 1, 90)
                             if len(tx_df) > 0 else avg_daily)
        budget_used_pct = spend_mtd / max(budget_total, 1)
        shortfall_prob = _rule_based_shortfall_prob(progress, budget_used_pct, delta)
        model_used = False

    #  Projections 
    avg_daily_spend = spend_mtd / max(day, 1)
    predicted_total_spend    = avg_daily_spend * days_in_month
    remaining_spend          = predicted_total_spend - spend_mtd

    # Internal Projected Income logic (used for smarter shortfall calculation)
    projected_income = 0.0
    if len(tx_df) > 0:
        salary_history = tx_df[(tx_df["type"] == "income") & (tx_df["category"].str.lower() == "salary")]
        if not salary_history.empty:
            avg_salary = salary_history["amount"].mean()
            # If no salary seen this month yet and before 28th
            if inc_mtd[inc_mtd["category"].str.lower() == "salary"].empty and day < 28:
                projected_income = float(avg_salary)

    # Shortfall = (Current Balance + Projected Income) - (Remaining Spend + Obligations)
    predicted_month_end_balance = (total_balance + projected_income) - remaining_spend - essential_total
    
    budget_overshoot_amount  = max(predicted_total_spend - budget_total, 0.0)
    budget_overshoot_percent = budget_overshoot_amount / max(budget_total, 1.0)

    #  Top risky categories 
    top_risky = []
    if len(exp_mtd) > 0:
        cat_spend = exp_mtd.groupby("category")["amount"].sum().sort_values(ascending=False)
        for cat, spent in cat_spend.head(3).items():
            days_remaining = days_in_month - day
            daily_cat = spent / max(day, 1)
            projected_cat = daily_cat * days_in_month
            # Compare vs budget if available
            budget_cat = float(budget_by_cat.get(cat, budget_total * 0.25))
            top_risky.append({
                "category":              cat,
                "current_spent":         float(spent),
                "avg_spent_last_3_months": float(projected_cat * 0.8),  # approx
                "projected_spent":       float(projected_cat),
            })

    #  Risk level 
    if shortfall_prob > 0.75 or budget_overshoot_percent > 0.30:
        risk_level = "high"
    elif shortfall_prob > 0.45 or budget_overshoot_percent > 0.15:
        risk_level = "medium"
    else:
        risk_level = "low"

    return {
        "shortfall_prob":               round(shortfall_prob, 4),
        "risk_level":                   risk_level,
        "predicted_total_spend":        round(predicted_total_spend, 2),
        "predicted_month_end_balance":  round(predicted_month_end_balance, 2),
        "budget_total":                 budget_total,
        "budget_overshoot_amount":      round(budget_overshoot_amount, 2),
        "budget_overshoot_percent":     round(budget_overshoot_percent, 4),
        "spend_mtd":                    round(spend_mtd, 2),
        "income_mtd":                   round(income_mtd, 2),
        "progress":                     round(progress, 4),
        "budget_used_pct":              round(spend_mtd / max(budget_total, 1), 4),
        "top_risky_categories":         top_risky,
        "essential_total":              essential_total,
        "model_was_used":               model_used,
    }
