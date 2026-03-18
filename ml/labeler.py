"""
ml/labeler.py

Defines the "shortfall event" label for each (user_id, year_month) pair.

A shortfall event (label=1) occurs when:
  - Total expenses for the month exceed the user's synthetic budget by > 10%
  - OR month-end indicators suggest the user cannot cover obligations

The synthetic budget is the rolling median of total_expense from the
last N months for that user (or global median if insufficient history).

This function works on BOTH:
  - Real CSV transactions (transactions_rows.csv)
  - Normalised Kaggle data (from load_kaggle_data.py)
"""
import pandas as pd
import numpy as np


OVERSPEND_THRESHOLD = 1.10   # 110% of budget = shortfall
ROLLING_WINDOW = 3            # months of history to compute budget


def compute_monthly_totals(tx_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate transactions by (user_id, year_month).

    Input tx_df must have columns: user_id, year_month (str), amount, type
    Returns DataFrame with: user_id, year_month, total_expense, total_income
    """
    # Ensure year_month is string e.g. "2026-02"
    tx_df = tx_df.copy()
    if hasattr(tx_df["year_month"].iloc[0] if len(tx_df) > 0 else "", "strftime"):
        tx_df["year_month"] = tx_df["year_month"].astype(str)
    else:
        tx_df["year_month"] = tx_df["year_month"].astype(str).str[:7]

    expenses = (
        tx_df[tx_df["type"] == "expense"]
        .groupby(["user_id", "year_month"])["amount"]
        .sum()
        .reset_index()
        .rename(columns={"amount": "total_expense"})
    )
    incomes = (
        tx_df[tx_df["type"] == "income"]
        .groupby(["user_id", "year_month"])["amount"]
        .sum()
        .reset_index()
        .rename(columns={"amount": "total_income"})
    )
    monthly = pd.merge(expenses, incomes, on=["user_id", "year_month"], how="outer").fillna(0)
    monthly = monthly.sort_values(["user_id", "year_month"]).reset_index(drop=True)
    return monthly


def add_synthetic_budget(monthly_df: pd.DataFrame) -> pd.DataFrame:
    """
    For each (user, month) compute synthetic_budget = rolling median of
    total_expense over the previous ROLLING_WINDOW months.

    Falls back to global median for users with insufficient history.
    """
    df = monthly_df.copy()
    global_median = df["total_expense"].median()
    if pd.isna(global_median) or global_median == 0:
        global_median = 1_000_000   # 1M VND default

    budgets = []
    for user_id, group in df.groupby("user_id"):
        group = group.sort_values("year_month").reset_index(drop=True)
        for i, row in group.iterrows():
            # Look at previous months only (exclude current)
            hist = group.loc[:i-1, "total_expense"].values[-ROLLING_WINDOW:]
            if len(hist) >= 1:
                budget = float(np.median(hist))
            else:
                budget = global_median
            budgets.append(budget)
    df["synthetic_budget"] = budgets
    return df


def label_shortfall(monthly_df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds 'shortfall_event' column (0 or 1) to the monthly aggregated DataFrame.
    """
    df = add_synthetic_budget(monthly_df)
    df["shortfall_event"] = (
        (df["total_expense"] > df["synthetic_budget"] * OVERSPEND_THRESHOLD)
    ).astype(int)
    df["overspend_pct"] = (
        (df["total_expense"] - df["synthetic_budget"]) / (df["synthetic_budget"] + 1e-9)
    ).clip(lower=-1.0, upper=5.0)
    return df


def build_labelled_dataset(tx_df: pd.DataFrame) -> pd.DataFrame:
    """
    Full pipeline: transactions → monthly totals → labels.
    Returns a DataFrame indexed by (user_id, year_month) with label columns.
    """
    monthly = compute_monthly_totals(tx_df)
    labelled = label_shortfall(monthly)
    return labelled


if __name__ == "__main__":
    from ml.load_real_data import load_transactions
    tx = load_transactions()
    result = build_labelled_dataset(tx)
    print(result)
    print(f"\nShortfall rate: {result['shortfall_event'].mean():.1%}")
