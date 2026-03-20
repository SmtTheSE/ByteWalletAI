"""
app/services/function_tools.py

Callable "wallet tool" functions for Phase 1: NL Function Calling.
Each function can be invoked dynamically by the Gemini LLM via Function Calling.

These tools act as a live bridge between natural-language questions and
the real computed data in the user's wallet snapshot.
"""
from __future__ import annotations
import calendar
import logging
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger("function_tools")

# 
# Tool implementations — each receives the user snapshot as context
# 

def get_wallet_balance(snapshot: dict) -> dict:
    """Return the user's current total, banking, and cash balance."""
    balances = snapshot.get("balances", {})
    if hasattr(balances, "__dict__"):
        balances = balances.__dict__
    banking = float(balances.get("banking", 0.0))
    cash    = float(balances.get("cash", 0.0))
    return {
        "banking": banking,
        "cash": cash,
        "total": banking + cash,
        "currency": snapshot.get("currency", "VND"),
    }


def get_upcoming_obligations(snapshot: dict) -> dict:
    """Return a list of upcoming essential obligations (bills, rent, etc.)."""
    obligations = snapshot.get("essential_obligations", []) or []
    result = []
    for o in obligations:
        if isinstance(o, dict):
            result.append(o)
        elif hasattr(o, "__dict__"):
            result.append(o.__dict__)
    total = sum(float(r.get("amount", 0)) for r in result)
    return {
        "obligations": result,
        "total_due": total,
        "currency": snapshot.get("currency", "VND"),
    }


def get_predicted_burn_rate(snapshot: dict) -> dict:
    """Run full ML predict on the snapshot and return burn-rate stats."""
    from app.services.ml_service import run_prediction
    stats = run_prediction(snapshot)
    return {
        "risk_level":                  stats.get("risk_level"),
        "shortfall_probability":       stats.get("shortfall_prob"),
        "spend_month_to_date":         stats.get("spend_mtd"),
        "predicted_total_spend":       stats.get("predicted_total_spend"),
        "predicted_month_end_balance": stats.get("predicted_month_end_balance"),
        "budget_total":                stats.get("budget_total"),
        "budget_overshoot_amount":     stats.get("budget_overshoot_amount"),
        "budget_overshoot_percent":    stats.get("budget_overshoot_percent"),
        "currency":                    snapshot.get("currency", "VND"),
    }


def can_afford(snapshot: dict, amount: float, description: str = "") -> dict:
    """
    Simulate whether the user can afford an additional expense.

    Projects the month-end-balance if `amount` is added to spending,
    and determines whether a shortfall will occur.
    """
    from app.services.ml_service import run_prediction
    stats = run_prediction(snapshot)

    currency   = snapshot.get("currency", "VND")
    balance    = stats.get("predicted_month_end_balance", 0.0)
    overshoot  = stats.get("budget_overshoot_amount", 0.0)

    # Re-project with the extra expense
    new_month_end = balance - amount
    can         = new_month_end > 0

    # Generate smart suggestion
    if can:
        advice = (
            f"Based on current spending patterns, a purchase of {amount:,.0f} {currency} "
            f"({description}) is affordable. Projected month-end balance: {new_month_end:,.0f} {currency}."
        )
    else:
        shortfall_amount = abs(new_month_end)
        advice = (
            f"This purchase of {amount:,.0f} {currency} ({description}) would cause a shortfall "
            f"of {shortfall_amount:,.0f} {currency} by month-end. "
            f"To absorb it, spending in other categories would need to be reduced by "
            f"approximately {shortfall_amount / max((snapshot.get('monthly_budget') or {}).get('total', 1) if not hasattr(snapshot.get('monthly_budget'), '__dict__') else getattr(snapshot.get('monthly_budget'), 'total', 1), 1) * 100:.1f}%."
        )
    return {
        "affordable": can,
        "additional_expense": amount,
        "description": description,
        "projected_month_end_balance_after": round(new_month_end, 2),
        "current_budget_overshoot": round(overshoot, 2),
        "advice": advice,
        "currency": currency,
    }


def get_spending_breakdown(snapshot: dict) -> dict:
    """Return a category-level spending breakdown for the current month."""
    import pandas as pd
    raw_txs = snapshot.get("transactions", []) or []
    current_date = pd.to_datetime(snapshot.get("current_date", datetime.now(timezone.utc).date()))
    year, month  = current_date.year, current_date.month
    month_start  = pd.Timestamp(year=year, month=month, day=1, tz="UTC")
    month_end    = pd.Timestamp(current_date.date(), tz="UTC")

    rows = []
    for t in raw_txs:
        if not isinstance(t, dict):
            t = t.__dict__ if hasattr(t, "__dict__") else {}
        ts  = pd.to_datetime(t.get("timestamp", current_date), utc=True, errors="coerce")
        amt = abs(float(t.get("amount", 0)))
        typ = str(t.get("type", "expense")).lower()
        cat = str(t.get("category", "Other"))
        rows.append({"timestamp": ts, "amount": amt, "type": typ, "category": cat})

    if not rows:
        return {"breakdown": {}, "total_spend": 0, "currency": snapshot.get("currency", "VND")}

    import pandas as pd  # noqa: F811
    df = pd.DataFrame(rows)
    mtd = df[(df["timestamp"] >= month_start) & (df["timestamp"] <= month_end) & (df["type"] == "expense")]
    breakdown = mtd.groupby("category")["amount"].sum().sort_values(ascending=False).to_dict()
    return {
        "breakdown": {k: round(v, 2) for k, v in breakdown.items()},
        "total_spend": round(mtd["amount"].sum(), 2),
        "currency": snapshot.get("currency", "VND"),
    }


# 
# Tool registry — maps function names to callables for the LLM dispatcher
# 

TOOL_REGISTRY: dict[str, Any] = {
    "get_wallet_balance":       get_wallet_balance,
    "get_upcoming_obligations": get_upcoming_obligations,
    "get_predicted_burn_rate":  get_predicted_burn_rate,
    "can_afford":               can_afford,
    "get_spending_breakdown":   get_spending_breakdown,
}

# Gemini function declaration schemas
GEMINI_TOOL_DECLARATIONS = [
    {
        "name": "get_wallet_balance",
        "description": "Get the user's current banking and cash balances.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_upcoming_obligations",
        "description": "Get all upcoming essential bills, rent, and financial obligations.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_predicted_burn_rate",
        "description": "Run the full AI burn-rate prediction and get risk level, shortfall probability, and end-of-month projections.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "can_afford",
        "description": "Determine whether the user can afford a specific additional expense given their current spending patterns.",
        "parameters": {
            "type": "object",
            "properties": {
                "amount": {"type": "number", "description": "The cost of the item or experience in the user's currency."},
                "description": {"type": "string", "description": "A human-readable name for the purchase (e.g. 'BlackPink concert tickets')."},
            },
            "required": ["amount"],
        },
    },
    {
        "name": "get_spending_breakdown",
        "description": "Get a detailed breakdown of spending by category for the current month.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
]
