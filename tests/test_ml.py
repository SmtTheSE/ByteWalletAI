"""
tests/test_ml.py

Unit tests for the ML pipeline (labeler, features, inference_core).
Run with:  cd bytewallet_ai && python -m pytest tests/test_ml.py -v
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from ml.labeler import build_labelled_dataset, compute_monthly_totals
from ml.features import build_inference_features, FEATURE_COLUMNS
from ml.inference_core import predict_burn_risk_from_snapshot


#  Labeler tests 

def _make_tx(user_id, year_month, amount, tx_type, day=15):
    return {"user_id": user_id, "year_month": year_month,
            "day": day, "amount": amount, "type": tx_type, "category": "Food"}


def test_monthly_totals():
    """Monthly totals should correctly sum expenses and income."""
    rows = [
        _make_tx("u1", "2024-01", 500_000, "expense"),
        _make_tx("u1", "2024-01", 300_000, "expense"),
        _make_tx("u1", "2024-01", 2_000_000, "income"),
    ]
    tx_df = pd.DataFrame(rows)
    monthly = compute_monthly_totals(tx_df)
    row = monthly[monthly["user_id"] == "u1"].iloc[0]
    assert row["total_expense"] == pytest.approx(800_000)
    assert row["total_income"]  == pytest.approx(2_000_000)


def test_label_shortfall():
    """A month where spend >> rolling median should be labelled 1."""
    # 3 normal months, then one big overspend month
    rows = []
    for m in ["2024-01","2024-02","2024-03"]:
        rows += [_make_tx("u1", m, 1_000_000, "expense"),
                 _make_tx("u1", m, 3_000_000, "income")]
    # Big overspend in April
    rows += [_make_tx("u1", "2024-04", 2_500_000, "expense"),   # 150% of 1M budget
             _make_tx("u1", "2024-04", 3_000_000, "income")]
    tx_df = pd.DataFrame(rows)
    labels = build_labelled_dataset(tx_df)
    april = labels[(labels["user_id"] == "u1") & (labels["year_month"] == "2024-04")]
    assert len(april) == 1
    assert april["shortfall_event"].values[0] == 1


def test_label_no_shortfall():
    """A normal-spend month should be labelled 0."""
    rows = []
    for m in ["2024-01","2024-02","2024-03","2024-04"]:
        rows += [_make_tx("u1", m, 1_000_000, "expense"),
                 _make_tx("u1", m, 3_000_000, "income")]
    tx_df = pd.DataFrame(rows)
    labels = build_labelled_dataset(tx_df)
    april = labels[(labels["user_id"] == "u1") & (labels["year_month"] == "2024-04")]
    assert april["shortfall_event"].values[0] == 0


#  Feature engineering tests 

def test_inference_features_shape():
    """build_inference_features must return a single-row df with all feature columns."""
    snapshot = {
        "current_date": "2026-03-15",
        "balances": {"banking": 5_000_000, "cash": 0},
        "monthly_budget": {"total": 7_000_000},
        "essential_obligations": [],
        "transactions": [
            {"timestamp": f"2026-03-{d:02d}T10:00:00Z",
             "amount": 200_000, "category": "Food", "type": "expense"}
            for d in range(1, 16)
        ],
    }
    df = build_inference_features(snapshot)
    assert len(df) == 1
    for col in FEATURE_COLUMNS:
        assert col in df.columns, f"Missing feature column: {col}"


def test_inference_features_progress():
    """Progress should be day/days_in_month."""
    snapshot = {
        "current_date": "2026-03-15",   # day 15 of 31
        "balances": {"banking": 1_000_000, "cash": 0},
        "monthly_budget": {"total": 5_000_000},
        "essential_obligations": [],
        "transactions": [],
    }
    df = build_inference_features(snapshot)
    expected = 15 / 31
    assert df["progress"].values[0] == pytest.approx(expected, abs=0.01)


#  Inference core tests 

def test_predict_high_risk():
    """High daily spend in first half → high or medium risk."""
    snapshot = {
        "user_id": "u_test",
        "current_date": "2026-03-14",
        "balances": {"banking": 500_000, "cash": 0},
        "monthly_budget": {"total": 7_000_000},
        "essential_obligations": [{"name": "Rent", "due_date": "2026-03-30", "amount": 5_000_000}],
        "transactions": [
            {"timestamp": f"2026-03-{d:02d}T10:00:00Z",
             "amount": 400_000, "category": "Food", "type": "expense"}
            for d in range(1, 15)
        ],
    }
    result = predict_burn_risk_from_snapshot(snapshot)
    assert result["risk_level"] in ("medium", "high")
    assert 0.0 <= result["shortfall_prob"] <= 1.0


def test_predict_low_risk():
    """Low daily spend → low risk."""
    snapshot = {
        "user_id": "u_test2",
        "current_date": "2026-03-14",
        "balances": {"banking": 15_000_000, "cash": 0},
        "monthly_budget": {"total": 7_000_000},
        "essential_obligations": [],
        "transactions": [
            {"timestamp": f"2026-03-{d:02d}T10:00:00Z",
             "amount": 80_000, "category": "Food", "type": "expense"}
            for d in range(1, 15)
        ] + [
            {"timestamp": "2026-03-01T08:00:00Z", "amount": 28_000_000,
             "category": "Salary", "type": "income"}
        ]
    }
    result = predict_burn_risk_from_snapshot(snapshot)
    assert result["risk_level"] in ("low", "medium", "high")
    assert 0.0 <= result["shortfall_prob"] <= 1.0
