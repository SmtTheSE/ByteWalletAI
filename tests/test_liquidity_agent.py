"""
tests/test_liquidity_agent.py

Verification for "Condition-1" LiquidityAgent logic.
"""
import pytest
from app.agents.liquidity_agent import LiquidityAgent

def test_liquidity_shortfall_detection():
    agent = LiquidityAgent()
    user_id = "test-user-liq"
    
    # Payload: 1.5M balance, but 2M in extra spend projected, and 1M in obligations
    # Projected Balance = 1.5M - 2M = -0.5M
    # Shortfall = 1M - (-0.5M) = 1.5M
    snapshot = {
        "currency": "VND",
        "balances": {"banking": 1_500_000, "cash": 0},
        "essential_obligations": [
            {"name": "Tuition Fee", "amount": 1_000_000, "due_date": "2026-03-30"}
        ],
        "transactions": [
            {"timestamp": "2026-03-01T10:00:00Z", "amount": 200_000, "category": "Shopping", "type": "expense"},
            {"timestamp": "2026-03-10T10:00:00Z", "amount": 200_000, "category": "Shopping", "type": "expense"},
            # Total 400k in 10 days -> 40k/day -> 1.2M in 30 days
        ]
    }
    
    alerts = agent.run(user_id, snapshot)
    
    assert len(alerts) > 0
    alert = alerts[0]
    assert alert.type == "liquidity"
    assert "Tuition Fee" in alert.message or "bills" in alert.message.lower()
    assert "shopping" in alert.suggested_action.lower()
    print(f"Alert Message: {alert.message}")
    print(f"Suggested Action: {alert.suggested_action}")

def test_no_liquidity_risk():
    agent = LiquidityAgent()
    user_id = "test-user-safe"
    
    # High balance, low obligations
    snapshot = {
        "currency": "VND",
        "balances": {"banking": 10_000_000, "cash": 0},
        "essential_obligations": [
            {"name": "Netflix", "amount": 200_000, "due_date": "2026-03-30"}
        ],
        "transactions": [
            {"timestamp": "2026-03-01T10:00:00Z", "amount": 50_000, "category": "Food", "type": "expense"}
        ]
    }
    
    alerts = agent.run(user_id, snapshot)
    assert len(alerts) == 0 # No shortfall expected
