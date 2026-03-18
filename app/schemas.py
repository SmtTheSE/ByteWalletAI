"""
app/schemas.py
Pydantic request / response models for the ByteWallet AI API.
"""
from __future__ import annotations
from datetime import datetime
from typing import List, Optional, Dict
from pydantic import BaseModel, Field


# ─────────────────────────── Request model ────────────────────────────────── #

class Transaction(BaseModel):
    timestamp: datetime
    amount: float = Field(..., gt=0, description="Positive amount in local currency")
    category: str
    type: str = Field(..., description="'expense' | 'income' | 'transfer'")
    note: Optional[str] = None
    payment_method: Optional[str] = None


class EssentialObligation(BaseModel):
    name: str
    due_date: str          # e.g. "2026-03-30"
    amount: float


class Balances(BaseModel):
    banking: float = 0.0
    cash: float = 0.0


class MonthlyBudget(BaseModel):
    total: float
    by_category: Optional[Dict[str, float]] = None


class PredictBurnRateRequest(BaseModel):
    user_id: str
    nickname: Optional[str] = None
    currency: str = "VND"
    current_date: str = Field(..., description="ISO date string, e.g. '2026-03-15'")
    ai_mode: str = Field(default="auto", description="'auto' | 'local_only' | 'rules_only'")
    balances: Balances
    monthly_budget: MonthlyBudget
    essential_obligations: List[EssentialObligation] = []
    transactions: List[Transaction] = Field(..., description="At least current-month transactions; more = better")


# ─────────────────────────── Response model ───────────────────────────────── #

class RiskyCategory(BaseModel):
    category: str
    current_spent: float
    avg_spent_last_3_months: float
    projected_spent: float


class TriggerRuleFlags(BaseModel):
    day_fraction: float
    budget_used_percent: float
    hit_15th_65_percent_rule: bool


class PredictBurnRateResponse(BaseModel):
    user_id: str
    currency: str
    risk_level: str                       # "low" | "medium" | "high"
    shortfall_prob: float
    predicted_month_end_balance: float
    predicted_total_spend: float
    budget_total: float
    budget_overshoot_amount: float
    budget_overshoot_percent: float
    trigger_rule: Optional[str]           # "15th_65_percent" or None
    trigger_rule_flags: TriggerRuleFlags
    top_risky_categories: List[RiskyCategory]
    ai_message: str
    ai_mode_used: str                     # "local_ollama" | "rules_only"
    generated_at: datetime
