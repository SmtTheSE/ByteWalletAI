"""
tests/test_universal_agents.py

Comprehensive verification for the Universal Wallet Intelligence suite.
"""
import pytest
import asyncio
from unittest.mock import MagicMock
from app.agents.income_agent import IncomeAgent
from app.agents.goal_agent import GoalAgent
from app.services.messaging_service import generate_ai_message

def test_income_late_alert():
    agent = IncomeAgent()
    # Mock date: 2026-03-20. Hist: Income arrived on 1st of Jan, Feb.
    # Arrival on 1st + 5 days = 6th. It's now the 20th. -> Late.
    snapshot = {
        "current_date": "2026-03-20",
        "transactions": [
            {"timestamp": "2026-01-01T10:00:00Z", "amount": 5000000, "type": "income"},
            {"timestamp": "2026-02-01T10:00:00Z", "amount": 5000000, "type": "income"},
        ]
    }
    alerts = agent.run("u1", snapshot)
    assert len(alerts) > 0
    assert "late" in alerts[0].title.lower()

def test_goal_progress_alert():
    agent = GoalAgent()
    snapshot = {
        "currency": "VND",
        "balances": {"banking": 9_000_000, "cash": 0},
        "savings_goals": [
            {"name": "New Phone", "target": 10_000_000}
        ]
    }
    alerts = agent.run("u1", snapshot)
    assert len(alerts) > 0
    assert "Almost there" in alerts[0].title

def test_messaging_priority_integration():
    # Liquidity (Critical) vs Goal (Info)
    # Liquidity should win in the rules-only message.
    stats = {"risk_level": "medium", "top_risky_categories": []}
    alerts = [
        {"type": "goal", "severity": "info", "message": "Goal is good.", "suggested_action": "Keep it up."},
        {"type": "liquidity", "severity": "critical", "message": "Wallet empty!", "suggested_action": "Stop spending."}
    ]
    
    msg, mode = generate_ai_message("Sitt", "VND", stats, {}, "rules_only", alerts)
    assert "Wallet empty!" in msg
    assert "Goal is good" not in msg # Priority 0 vs Priority 5
