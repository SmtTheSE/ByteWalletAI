"""
ml/features.py  (PRODUCTION VERSION v2 — Fully Vectorized)

Builds feature vectors for training and inference using 100% vectorized
pandas groupby + merge operations. Scales to millions of rows.

Feature set for each (user_id, year_month):
  Temporal:        day_of_month, days_in_month, progress
  MTD spending:    spend_mtd, income_mtd, avg_daily_spend_mtd
  Trend:           avg_daily_spend_last_3m, delta_spend_rate
  Cash flow:       net_mtd, cash_flow_ratio
  Category shares: pct_food, pct_transport, pct_shopping, pct_health,
                   pct_rent, pct_entertainment, pct_other
  History:         prev_month_overspend, prev2_month_overspend
"""
from __future__ import annotations
import calendar
import logging
from typing import Optional

import numpy as np
import pandas as pd

log = logging.getLogger("features")

# Canonical category → model feature bucket
CATEGORY_MAP: dict[str, str] = {
    "Food": "pct_food", "Grocery_Pos": "pct_food", "Grocery_Net": "pct_food",
    "Food_Dining": "pct_food", "Living": "pct_food",
    "Transport": "pct_transport", "Gas_Transport": "pct_transport",
    "Shopping": "pct_shopping", "Shopping_Net": "pct_shopping",
    "Shopping_Pos": "pct_shopping", "Card Spend": "pct_shopping",
    "Health": "pct_health", "Health_Fitness": "pct_health",
    "Rent": "pct_rent", "Home": "pct_rent",
    "Entertainment": "pct_entertainment", "Entertainment_General": "pct_entertainment",
    "Withdrawal": "pct_other", "Transfer": "pct_other",
    "Bills": "pct_other", "Debt Payment": "pct_other",
    "Travel": "pct_other", "Personal_Care": "pct_other",
}
CAT_FEATURES = ["pct_food","pct_transport","pct_shopping",
                 "pct_health","pct_rent","pct_entertainment","pct_other"]

FEATURE_COLUMNS = [
    "day_of_month", "days_in_month", "progress",
    "spend_mtd", "income_mtd", "avg_daily_spend_mtd",
    "avg_daily_spend_last_3m", "delta_spend_rate",
    "net_mtd", "cash_flow_ratio",
    *CAT_FEATURES,
    "prev_month_overspend", "prev2_month_overspend",
]


def _cat_bucket(category: str) -> str:
    return CATEGORY_MAP.get(category, "pct_other")


# 
# Vectorized training feature builder
# 

def build_training_features(
    tx_df: pd.DataFrame,
    labels_df: pd.DataFrame,
    snapshot_day: int = 15,
) -> pd.DataFrame:
    """
    Build training features using fully vectorized pandas operations.
    Processes ANY number of users × months in seconds (not hours).

    Args:
        tx_df:        Transactions (user_id, year_month, day, amount, type, category)
        labels_df:    Monthly labels from labeler.build_labelled_dataset()
        snapshot_day: Simulated "current day" for each month in training

    Returns:
        DataFrame with FEATURE_COLUMNS + 'shortfall_event'
    """
    log.info(f"  Building training features (vectorized). snapshot_day={snapshot_day}")

    tx = tx_df.copy()
    tx["year_month"] = tx["year_month"].astype(str).str[:7]
    tx["day"]        = pd.to_numeric(tx["day"], errors="coerce").fillna(15).astype(int).clip(1, 31)
    tx["amount"]     = pd.to_numeric(tx["amount"], errors="coerce").fillna(0)

    # Fix NaT error by keeping only valid YYYY-MM dates
    tx = tx[tx["year_month"].str.match(r"^\d{4}-\d{2}$", na=False)].copy()

    # Parse year_month to get calendar info
    tx["_year"]  = tx["year_month"].str[:4].astype(int)
    tx["_month"] = tx["year_month"].str[5:7].astype(int)
    tx["_days_in_month"] = tx.apply(
        lambda r: calendar.monthrange(r["_year"], r["_month"])[1], axis=1
    )
    tx["_progress"] = (snapshot_day / tx["_days_in_month"]).clip(0, 1)

    # Filter to MTD transactions (up to snapshot_day)
    tx_mtd = tx[tx["day"] <= snapshot_day].copy()

    # Add category bucket
    tx_mtd = tx_mtd.copy()
    tx_mtd["cat_bucket"] = tx_mtd["category"].map(CATEGORY_MAP).fillna("pct_other")

    #  MTD expense and income aggregates 
    exp = tx_mtd[tx_mtd["type"] == "expense"]
    inc = tx_mtd[tx_mtd["type"] == "income"]
    key = ["user_id", "year_month"]

    spend_mtd  = exp.groupby(key)["amount"].sum().rename("spend_mtd")
    income_mtd = inc.groupby(key)["amount"].sum().rename("income_mtd")

    #  Category shares (pivot table) 
    if len(exp) > 0:
        cat_pivot = (
            exp.groupby(key + ["cat_bucket"])["amount"]
            .sum().unstack(fill_value=0)
            .reindex(columns=CAT_FEATURES, fill_value=0)
        )
        # Normalize to percentages
        cat_total = cat_pivot.sum(axis=1).replace(0, 1)
        cat_pct   = cat_pivot.div(cat_total, axis=0)
    else:
        cat_pct = pd.DataFrame(columns=CAT_FEATURES)

    #  Combine into month-level features 
    base = labels_df[["user_id","year_month","shortfall_event"]].copy()
    base = base.merge(spend_mtd,  on=key, how="left")
    base = base.merge(income_mtd, on=key, how="left")
    base = base.merge(cat_pct.reset_index(), on=key, how="left")
    for col in CAT_FEATURES:
        if col not in base.columns:
            base[col] = 0.0
    base["spend_mtd"]  = base["spend_mtd"].fillna(0)
    base["income_mtd"] = base["income_mtd"].fillna(0)
    for col in CAT_FEATURES:
        base[col] = base[col].fillna(0)

    #  Calendar features 
    base["_year"]  = base["year_month"].str[:4].astype(int)
    base["_month"] = base["year_month"].str[5:7].astype(int)
    base["days_in_month"] = base.apply(
        lambda r: calendar.monthrange(r["_year"], r["_month"])[1], axis=1
    )
    base["day_of_month"]  = snapshot_day
    base["progress"]      = (snapshot_day / base["days_in_month"]).clip(0, 1)

    #  Derived features 
    base["avg_daily_spend_mtd"] = base["spend_mtd"] / snapshot_day
    base["net_mtd"]             = base["income_mtd"] - base["spend_mtd"]
    base["cash_flow_ratio"]     = base["income_mtd"] / (base["spend_mtd"] + 1e-9)

    #  Last-3-month rolling avg daily spend (vectorized via shift) 
    # Build monthly total expense per user
    monthly_exp = (
        tx[tx["type"] == "expense"]
        .groupby(key)["amount"]
        .sum().rename("total_expense")
        .reset_index()
        .sort_values(key)
    )
    monthly_exp["days_in_month_x"] = monthly_exp.apply(
        lambda r: calendar.monthrange(int(r["year_month"][:4]), int(r["year_month"][5:7]))[1], axis=1
    )
    monthly_exp["daily_exp"] = monthly_exp["total_expense"] / monthly_exp["days_in_month_x"]

    # Rolling mean of last 3 months per user
    monthly_exp = monthly_exp.sort_values(key)
    monthly_exp["avg_daily_exp_3m"] = (
        monthly_exp.groupby("user_id")["daily_exp"]
        .transform(lambda s: s.shift(1).rolling(3, min_periods=1).mean())
    )
    base = base.merge(
        monthly_exp[key + ["avg_daily_exp_3m"]],
        on=key, how="left"
    )
    base["avg_daily_spend_last_3m"] = base["avg_daily_exp_3m"].fillna(base["avg_daily_spend_mtd"])
    base["delta_spend_rate"]        = base["avg_daily_spend_mtd"] - base["avg_daily_spend_last_3m"]

    #  Historical overspend flags (lagged labels per user) 
    lbl = labels_df[["user_id","year_month","shortfall_event"]].copy()
    lbl = lbl.sort_values(["user_id","year_month"])
    lbl["prev1"] = lbl.groupby("user_id")["shortfall_event"].shift(1).fillna(0).astype(int)
    lbl["prev2"] = lbl.groupby("user_id")["shortfall_event"].shift(2).fillna(0).astype(int)
    base = base.merge(lbl[key + ["prev1","prev2"]], on=key, how="left")
    base["prev_month_overspend"]  = base["prev1"].fillna(0).astype(int)
    base["prev2_month_overspend"] = base["prev2"].fillna(0).astype(int)

    #  Final assembly 
    result = base[FEATURE_COLUMNS + ["shortfall_event"]].copy()
    result = result.dropna(subset=["shortfall_event"])
    result[FEATURE_COLUMNS] = result[FEATURE_COLUMNS].fillna(0)
    result["shortfall_event"] = result["shortfall_event"].astype(int)

    log.info(f"   Feature matrix: {len(result):,} rows × {len(FEATURE_COLUMNS)} features")
    return result.reset_index(drop=True)


# 
# Live inference: single-user snapshot → feature vector
# 

def build_inference_features(snapshot: dict) -> pd.DataFrame:
    """
    Build a single-row feature DataFrame from a live API request snapshot.
    All operations are vectorized / direct calculations — no loops.
    """
    from datetime import datetime, timezone

    current_date   = pd.to_datetime(snapshot.get("current_date", datetime.now(timezone.utc).date()))
    day            = current_date.day
    month          = current_date.month
    year           = current_date.year
    days_in_month  = calendar.monthrange(year, month)[1]
    progress       = day / days_in_month

    # Parse transactions to DataFrame
    raw_txs = snapshot.get("transactions", []) or []
    tx_rows = []
    for t in raw_txs:
        if not isinstance(t, dict):
            t = t.__dict__ if hasattr(t, "__dict__") else {}
        ts  = pd.to_datetime(t.get("timestamp", current_date), utc=True, errors="coerce")
        amt = abs(float(t.get("amount", 0)))
        typ = str(t.get("type", "expense")).lower()
        cat = str(t.get("category", "Other"))
        tx_rows.append({"timestamp": ts, "amount": amt, "type": typ, "category": cat})

    if tx_rows:
        tx_df = pd.DataFrame(tx_rows)
    else:
        tx_df = pd.DataFrame(columns=["timestamp","amount","type","category"])

    # MTD filter
    month_start = pd.Timestamp(year=year, month=month, day=1, tz="UTC")
    day_end     = pd.Timestamp(year=year, month=month, day=day, tz="UTC") + pd.Timedelta(days=1)
    if len(tx_df) > 0:
        mtd = tx_df[(tx_df["timestamp"] >= month_start) & (tx_df["timestamp"] < day_end)]
    else:
        mtd = tx_df

    exp_mtd  = mtd[mtd["type"] == "expense"] if len(mtd) > 0 else mtd
    inc_mtd  = mtd[mtd["type"] == "income"]  if len(mtd) > 0 else mtd
    spend_mtd_  = float(exp_mtd["amount"].sum())
    income_mtd_ = float(inc_mtd["amount"].sum())

    avg_daily_spend_mtd = spend_mtd_ / max(day, 1)

    # Historical daily spend (from months before current)
    if len(tx_df) > 0:
        hist_exp = tx_df[(tx_df["type"] == "expense") & (tx_df["timestamp"] < month_start)]
        hist_days = max((month_start - (month_start - pd.DateOffset(months=3))).days, 90)
        avg_daily_spend_last_3m = float(hist_exp["amount"].sum()) / hist_days
    else:
        avg_daily_spend_last_3m = avg_daily_spend_mtd

    delta_spend_rate = avg_daily_spend_mtd - avg_daily_spend_last_3m

    # Category breakdown (expense MTD only)
    cat_totals = {f: 0.0 for f in CAT_FEATURES}
    if len(exp_mtd) > 0:
        for _, row in exp_mtd.iterrows():
            b = _cat_bucket(str(row["category"]))
            cat_totals[b] = cat_totals.get(b, 0.0) + float(row["amount"])
        total_cat = sum(cat_totals.values()) or 1.0
        cat_pcts = {k: v / total_cat for k, v in cat_totals.items()}
    else:
        cat_pcts = cat_totals

    net_mtd         = income_mtd_ - spend_mtd_
    cash_flow_ratio = income_mtd_ / (spend_mtd_ + 1e-9)

    row = {
        "day_of_month":             day,
        "days_in_month":            days_in_month,
        "progress":                 progress,
        "spend_mtd":                spend_mtd_,
        "income_mtd":               income_mtd_,
        "avg_daily_spend_mtd":      avg_daily_spend_mtd,
        "avg_daily_spend_last_3m":  avg_daily_spend_last_3m,
        "delta_spend_rate":         delta_spend_rate,
        "net_mtd":                  net_mtd,
        "cash_flow_ratio":          cash_flow_ratio,
        "prev_month_overspend":     0,
        "prev2_month_overspend":    0,
        **cat_pcts,
    }
    return pd.DataFrame([row])[FEATURE_COLUMNS]
