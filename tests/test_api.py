"""
tests/test_api.py

Integration tests for POST /v1/predict-burn-rate.
Run with:  cd bytewallet_ai && python -m pytest tests/ -v
"""
import pytest
from fastapi.testclient import TestClient

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import app

client = TestClient(app)


# ─── Fixtures ────────────────────────────────────────────────────────────────

def _high_risk_payload():
    """User has used 72% of budget by day 14 (first half of month)."""
    return {
        "user_id":      "test-user-001",
        "nickname":     "Ku Kue",
        "currency":     "VND",
        "current_date": "2026-03-14",
        "ai_mode":      "rules_only",
        "balances":     {"banking": 1_500_000, "cash": 0},
        "monthly_budget": {
            "total":       7_000_000,
            "by_category": {"Food": 2_000_000, "Shopping": 2_000_000, "Transport": 1_000_000}
        },
        "essential_obligations": [
            {"name": "Rent", "due_date": "2026-03-30", "amount": 5_000_000}
        ],
        "transactions": [
            # 14 days × ~357k/day = ~5,000,000 = 71% of 7M budget
            {"timestamp": f"2026-03-{d:02d}T10:00:00Z", "amount": 357_000,
             "category": "Food", "type": "expense"}
            for d in range(1, 15)
        ] + [
            {"timestamp": "2026-03-01T08:00:00Z", "amount": 7_000_000,
             "category": "Salary", "type": "income"}
        ]
    }


def _low_risk_payload():
    """User has only used 18% of budget by day 14."""
    return {
        "user_id":      "test-user-002",
        "nickname":     "Zwe",
        "currency":     "VND",
        "current_date": "2026-03-14",
        "ai_mode":      "rules_only",
        "balances":     {"banking": 10_000_000, "cash": 500_000},
        "monthly_budget": {
            "total": 7_000_000,
            "by_category": {"Food": 2_000_000, "Shopping": 2_000_000}
        },
        "essential_obligations": [],
        "transactions": [
            {"timestamp": f"2026-03-{d:02d}T10:00:00Z", "amount": 90_000,
             "category": "Food", "type": "expense"}
            for d in range(1, 15)
        ] + [
            {"timestamp": "2026-03-01T08:00:00Z", "amount": 28_000_000,
             "category": "Salary", "type": "income"}
        ]
    }


# ─── Tests ───────────────────────────────────────────────────────────────────

def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"


def test_high_risk_response():
    """High-risk user → risk_level high, 15th/65% rule triggered, message returned."""
    res = client.post("/v1/predict-burn-rate", json=_high_risk_payload())
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["risk_level"] in ("medium", "high")
    assert data["trigger_rule_flags"]["hit_15th_65_percent_rule"] is True
    assert data["trigger_rule"] == "15th_65_percent"
    assert data["shortfall_prob"] >= 0.0
    assert isinstance(data["ai_message"], str)
    assert len(data["ai_message"]) > 10
    assert data["ai_mode_used"] == "rules_only"
    print(f"\n[HIGH-RISK] risk={data['risk_level']} prob={data['shortfall_prob']:.2f}")
    print(f"  Message: {data['ai_message']}")


def test_low_risk_response():
    """Low-risk user → risk_level low, no rule trigger, encouraging message."""
    res = client.post("/v1/predict-burn-rate", json=_low_risk_payload())
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["risk_level"] in ("low", "medium", "high")
    assert data["trigger_rule_flags"]["hit_15th_65_percent_rule"] is False
    assert data["trigger_rule"] is None
    assert isinstance(data["ai_message"], str)
    assert len(data["ai_message"]) > 10
    print(f"\n[LOW-RISK] risk={data['risk_level']} prob={data['shortfall_prob']:.2f}")
    print(f"  Message: {data['ai_message']}")


def test_missing_transactions():
    """API should still work with zero transactions."""
    payload = _low_risk_payload()
    payload["transactions"] = []
    res = client.post("/v1/predict-burn-rate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["risk_level"] in ("low", "medium", "high")


def test_response_shape():
    """Response must have all required fields."""
    res = client.post("/v1/predict-burn-rate", json=_high_risk_payload())
    assert res.status_code == 200
    data = res.json()
    required = [
        "user_id", "currency", "risk_level", "shortfall_prob",
        "predicted_month_end_balance", "predicted_total_spend",
        "budget_total", "budget_overshoot_amount", "budget_overshoot_percent",
        "trigger_rule_flags", "top_risky_categories",
        "ai_message", "ai_mode_used", "generated_at"
    ]
    for field in required:
        assert field in data, f"Missing field: {field}"
