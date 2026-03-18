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
) -> str:
    """
    Combine ML probability + overshoot % + rule flags into a final risk level.

    Returns: "low" | "medium" | "high"
    """
    if shortfall_prob > 0.75 or budget_overshoot_percent > 0.30:
        return "high"
    if shortfall_prob > 0.45 or budget_overshoot_percent > 0.15:
        # Elevate from medium to high if the 15th/65% rule fires
        if rule_result.hit_15th_65_percent_rule:
            return "high"
        return "medium"
    # Low baseline — but warn if rule fires
    if rule_result.hit_15th_65_percent_rule:
        return "medium"
    return "low"
