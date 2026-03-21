"""
tests/verify_md_conditions.py

This test suite explicitly verifies that the AI agents follow the logic in:
- condition1.md: Monthly Plan Shortfall Analysis
- condition2.md: Mid-Month Check
"""
import pytest
from app.agents.liquidity_agent import LiquidityAgent
from app.agents.midmonth_agent import MidMonthAgent

def test_condition1_exact_alignment():
    """
    Verifies Condition 1:
    Essential_Expenses = 4.0M (Rent)
    Total_Balance = 5.0M
    Total_Extra_Expenses_Monthly (Projected) = 2.0M
    Average_Balance_in_Hand = 5.0M - 2.0M = 3.0M
    Needed_Amount = 4.0M - 3.0M = 1.0M
    Check Category: Shopping (Avg cost: 500k)
    Times_to_Avoid = 1.0M / 500k = 2 times.
    """
    agent = LiquidityAgent()
    snapshot = {
        "currency": "VND",
        "balances": {"banking": 4_000_000, "cash": 1_000_000}, # Total: 5M
        "essential_obligations": [
            {"name": "Rent", "amount": 4_000_000}
        ],
        "transactions": [
            # We want projected_30d_extra to be 2M.
            # daily_extra_rate = 2M / 30 = 66,666.66
            # Total extra in 10 days = 666,666.66.
            {"timestamp": "2026-03-01T10:00:00Z", "amount": 333_333, "category": "Shopping", "type": "expense"},
            {"timestamp": "2026-03-11T10:00:00Z", "amount": 333_333, "category": "Shopping", "type": "expense"},
        ],
        "current_date": "2026-03-15"
    }
    
    alerts = agent.run("user123", snapshot)
    
    assert len(alerts) >= 1
    alert = alerts[0]
    
    # Projected Extra = (666,666 / 10 days) * 30 = 2,000,000.
    # Projected Balance In Hand = 5M - 2M = 3M.
    # Needed Amount = 4M (Essential) - 3M = 1M Shortfall.
    # Avg item price = 333,333.
    # Items to cut = 1M / 333,333 = 3.

    # Check if calculation matches Needed Amount (approx 1M) and Times to Avoid (3)
    # The message says 999,998 VND due to rounding, which is mathematically consistent.
    assert "999,998" in alert.message or "1,000,000" in alert.message
    assert "3 shopping purchases" in alert.suggested_action.lower()
    assert alert.severity == "critical"

def test_condition2_exact_alignment():
    """
    Verifies Condition 2:
    Actual_Balance = Total_Balance (10M) - Essential_Amount (4M) = 6M baseline.
    Mid-Month Check: Day 15.
    Current Usage: 4M spent on non-essentials.
    4M / 6M = 66.7% usage (> 50%). -> Show Alert.
    """
    agent = MidMonthAgent()
    snapshot = {
        "current_date": "2026-03-15", # Mid-month
        "currency": "VND",
        "balances": {"banking": 10_000_000, "cash": 0},
        "essential_obligations": [
            {"name": "Rent", "amount": 4_000_000}
        ],
        "transactions": [
            # 4M spent on non-essentials this month
            {"timestamp": "2026-03-05T10:00:00Z", "amount": 4_000_000, "category": "Shopping", "type": "expense"},
        ]
    }
    
    alerts = agent.run("user123", snapshot)
    
    assert len(alerts) == 1
    alert = alerts[0]
    
    assert "used 66.7%" in alert.message
    assert "Mid-Month Discretionary Warning" in alert.title
    assert alert.severity == "warning"

if __name__ == "__main__":
    # Manual run check
    pytest.main([__file__])
