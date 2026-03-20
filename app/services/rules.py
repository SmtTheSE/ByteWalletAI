"""
app/services/rules.py

Implements the 15th/65% Business Rule and risk level thresholds.

Rule: "If you're in the first half of the month and have already used
       65% or more of your budget, raise an alert."

This rule is a simple heuristic that fires regardless of what the ML model says.
It acts as an early-warning layer on top of the probabilistic output.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class RuleResult:
    hit_15th_65_percent_rule: bool
    day_fraction: float
    budget_used_percent: float
    trigger_rule: Optional[str]


def evaluate_rules(
    day_of_month: int,
    days_in_month: int,
    spend_mtd: float,
    budget_total: float,
) -> RuleResult:
    """
    Evaluate the 15th/65% rule and return a RuleResult.

    Args:
        day_of_month:  Current day in the month (1-31)
        days_in_month: Total days in the month (28-31)
        spend_mtd:     Month-to-date spending (expenses only)
        budget_total:  Total monthly budget

    Returns:
        RuleResult
    """
    day_fraction        = day_of_month / max(days_in_month, 1)
    budget_used_percent = spend_mtd / max(budget_total, 1.0)

    # 15th/65% rule: first half of month AND ≥ 65% budget used
    hit = (day_fraction <= 0.50) and (budget_used_percent >= 0.65)
    trigger_rule = "15th_65_percent" if hit else None

    return RuleResult(
        hit_15th_65_percent_rule=hit,
        day_fraction=round(day_fraction, 4),
        budget_used_percent=round(budget_used_percent, 4),
        trigger_rule=trigger_rule,
    )


def determine_risk_level(
    shortfall_prob: float,
    budget_overshoot_percent: float,
    rule_result: RuleResult,
    predicted_balance: float = 0.0,
) -> str:
    """
    Combine ML probability + overshoot % + rule flags into a final risk level.
    This logic is TRULY ADAPTIVE: It prioritizes Real-World Math (Projected Balance)
    to decide if a user is truly safe, regardless of what the probabilistic ML thinks.
    """
    # 1. Real-World Math Override (Individual Reality)
    # -----------------------------------------------
    # If the user is projected to have a SIGNIFICANT surplus (> 500k VND) 
    # and they aren't massive overshooting their budget, they are SAFE.
    if predicted_balance > 500000 and budget_overshoot_percent < 0.20:
        return "low"
    
    # If they are just barely safe (> 0), call it Medium to be cautious
    if predicted_balance > 0:
        return "medium"

    # 2. AI Driven Assessment (Dynamic Pacing)
    # ----------------------------------------
    if shortfall_prob > 0.85 or budget_overshoot_percent > 0.50:
        return "high"
    
    if shortfall_prob > 0.70 or budget_overshoot_percent > 0.25:
        return "high"

    # Medium Risk: Moderate indicators
    if shortfall_prob > 0.40 or budget_overshoot_percent > 0.10:
        # Static rule reinforcement
        if rule_result.hit_15th_65_percent_rule:
            return "high"
        return "medium"

    # 3. Heuristic Edge Cases
    # ------------------------
    if rule_result.hit_15th_65_percent_rule:
        return "medium"

    return "low"
