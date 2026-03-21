"""
tests/test_midmonth_agent.py

Verification for Condition-2 (Mid-Month Check).
"""
import pytest
from app.agents.midmonth_agent import MidMonthAgent

def test_midmonth_alert_triggered():
    agent = MidMonthAgent()
    # Mock date: 15th (Mid-month)
    # Total Balance: 10M
    # Essential: 4M (Rent)
    # Actual Balance Baseline (Discretionary) = 6M
    # Spent so far this month: 4M. 
    # Ratio = 4 / 6 = 66.7% (> 50%). -> Alert.
    snapshot = {
        "current_date": "2026-03-15",
        "currency": "VND",
        "balances": {"banking": 9_000_000, "cash": 1_000_000},
        "essential_obligations": [
            {"name": "Rent", "amount": 4_000_000}
        ],
        "transactions": [
            # Discretionary spending this month (March)
            {"timestamp": "2026-03-05T10:00:00Z", "amount": 2_000_000, "category": "Shopping", "type": "expense"},
            {"timestamp": "2026-03-10T10:00:00Z", "amount": 2_000_000, "category": "Food", "type": "expense"},
            # Essential spending (should be ignored for usage ratio)
            {"timestamp": "2026-03-01T10:00:00Z", "amount": 4_000_000, "category": "Rent", "type": "expense"},
        ]
    }
    alerts = agent.run("u1", snapshot)
    assert len(alerts) == 1
    assert "used 66.7%" in alerts[0].message
    assert alerts[0].severity == "warning"

def test_midmonth_no_alert_low_usage():
    agent = MidMonthAgent()
    # Baseline: 6M. Spent: 1M. Ratio: 16.6% (< 50%). -> No Alert.
    snapshot = {
        "current_date": "2026-03-15",
        "currency": "VND",
        "balances": {"banking": 10_000_000, "cash": 0},
        "essential_obligations": [{"name": "Rent", "amount": 4_000_000}],
        "transactions": [
            {"timestamp": "2026-03-05T10:00:00Z", "amount": 1_000_000, "category": "Shopping", "type": "expense"},
        ]
    }
    alerts = agent.run("u1", snapshot)
    assert len(alerts) == 0

def test_midmonth_ignored_if_not_midmonth():
    agent = MidMonthAgent()
    # 5th of the month.
    snapshot = {
        "current_date": "2026-03-05",
        "currency": "VND",
        "balances": {"banking": 10_000_000, "cash": 0},
        "essential_obligations": [{"name": "Rent", "amount": 4_000_000}],
        "transactions": [
            {"timestamp": "2026-03-02T10:00:00Z", "amount": 5_000_000, "category": "Shopping", "type": "expense"},
        ]
    }
    alerts = agent.run("u1", snapshot)
    assert len(alerts) == 0
