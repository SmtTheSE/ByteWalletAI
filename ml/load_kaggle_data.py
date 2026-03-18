"""
ml/load_kaggle_data.py  (PRODUCTION VERSION)

Loads and normalises all 4 real-world Kaggle datasets into a unified schema:
    user_id | year_month | amount | type (expense/income) | category

Real datasets used:
  1. credit_transactions  — 1M+ credit card transactions (category, amount, date)
  2. online_fraud         — PaySim mobile money (type, amount, fraud flag)
  3. credit_score         — Monthly income/expense snapshots per customer
  4. credit_fraud         — EU creditcard fraud (PCA features, amount)

These augment our real ByteWallet CSV data for training burn-rate models.
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

log = logging.getLogger("load_kaggle")
KAGGLE_DIR = Path(__file__).parent.parent / "data" / "kaggle"

# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _find_csv(folder: str) -> Optional[Path]:
    """Return the largest CSV file in the given subfolder, or None."""
    p = KAGGLE_DIR / folder
    if not p.exists():
        return None
    csvs = sorted(p.glob("**/*.csv"), key=lambda f: f.stat().st_size, reverse=True)
    return csvs[0] if csvs else None


def _to_unified(df: pd.DataFrame) -> pd.DataFrame:
    """Force schema: user_id, year_month (str YYYY-MM), amount (float), type, category."""
    required = ["user_id", "year_month", "amount", "type", "category"]
    for col in required:
        if col not in df.columns:
            df[col] = "unknown" if col in ("user_id", "year_month", "type", "category") else 0.0
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").abs().fillna(0)
    df = df[df["amount"] > 0]
    df["year_month"] = df["year_month"].astype(str).str[:7]
    df["type"] = df["type"].str.lower().map(
        {"expense": "expense", "income": "income", "transfer": "transfer",
         "debit": "expense", "credit": "income"}
    ).fillna("expense")
    return df[required].drop_duplicates().reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# Dataset 1: credit_card_transactions (category + amount + date, 1M+ rows)
# Schema: trans_date_trans_time, cc_num, merchant, category, amt, is_fraud
# ─────────────────────────────────────────────────────────────────────────────

def load_credit_transactions(max_rows: int = 200_000) -> Optional[pd.DataFrame]:
    f = _find_csv("credit_transactions")
    if f is None:
        log.warning("credit_transactions CSV not found")
        return None
    log.info(f"  Loading credit_transactions: {f.name} ({f.stat().st_size // 1_048_576}MB)")
    df = pd.read_csv(f, nrows=max_rows, low_memory=False)

    # Map to unified schema
    df["_date"]  = pd.to_datetime(df.get("trans_date_trans_time", df.get("date", "2023-01")),
                                   errors="coerce")
    df["_ym"]    = df["_date"].dt.to_period("M").astype(str)
    df["_uid"]   = df.get("cc_num", df.index).astype(str).apply(lambda x: f"cct_{hash(x) % 50_000}")
    df["_amt"]   = pd.to_numeric(df.get("amt", df.get("amount", 0)), errors="coerce").abs()
    df["_cat"]   = df.get("category", "general").fillna("general").str.title()
    df["_type"]  = "expense"

    # Also generate synthetic "income" entries (salary top-ups once a month per user)
    income_rows = (
        df.groupby(["_uid", "_ym"])["_amt"]
        .sum().reset_index()
        .rename(columns={"_amt": "_monthly_spend"})
    )
    income_rows["_amt"]  = income_rows["_monthly_spend"] * 1.5   # income ~150% of spend
    income_rows["_cat"]  = "Salary"
    income_rows["_type"] = "income"

    expense_df = df[["_uid","_ym","_amt","_type","_cat"]].copy()
    expense_df.columns = ["user_id","year_month","amount","type","category"]

    inc_df = income_rows[["_uid","_ym","_amt","_type","_cat"]].copy()
    inc_df.columns = ["user_id","year_month","amount","type","category"]

    combined = pd.concat([expense_df, inc_df], ignore_index=True)
    log.info(f"    → {len(combined):,} rows (expenses + synthetic income)")
    return _to_unified(combined)


# ─────────────────────────────────────────────────────────────────────────────
# Dataset 2: online_fraud (PaySim mobile money - CASH_IN, CASH_OUT, etc.)
# Schema: step, type, amount, nameOrig, oldbalanceOrg ... isFraud
# ─────────────────────────────────────────────────────────────────────────────

def load_online_fraud(max_rows: int = 150_000) -> Optional[pd.DataFrame]:
    f = _find_csv("online_fraud")
    if f is None:
        log.warning("online_fraud CSV not found")
        return None
    log.info(f"  Loading online_fraud: {f.name} ({f.stat().st_size // 1_048_576}MB)")
    df = pd.read_csv(f, nrows=max_rows, low_memory=False)

    # step = hour since simulation start; ~720 hours = 30 days
    df["_step"]  = pd.to_numeric(df.get("step", 0), errors="coerce").fillna(0)
    df["_month"] = ((df["_step"] // 720).astype(int).clip(0, 11) + 1)
    df["_ym"]    = df["_month"].apply(lambda m: f"2024-{m:02d}")
    df["_uid"]   = df.get("nameOrig", df.index).astype(str).apply(lambda x: f"psim_{hash(x) % 20_000}")
    df["_amt"]   = pd.to_numeric(df.get("amount", 0), errors="coerce").abs()

    # Map PaySim types to expense/income
    type_map = {
        "CASH_OUT": "expense",
        "PAYMENT":  "expense",
        "DEBIT":    "expense",
        "TRANSFER": "transfer",
        "CASH_IN":  "income",
    }
    df["_type"] = df.get("type", "PAYMENT").map(type_map).fillna("expense")

    # Category inference
    cat_map = {
        "CASH_OUT": "Withdrawal",
        "PAYMENT":  "Shopping",
        "DEBIT":    "Bills",
        "TRANSFER": "Transfer",
        "CASH_IN":  "Salary",
    }
    df["_cat"] = df.get("type", "PAYMENT").map(cat_map).fillna("Shopping")

    out = df[["_uid","_ym","_amt","_type","_cat"]].copy()
    out.columns = ["user_id","year_month","amount","type","category"]
    log.info(f"    → {len(out):,} rows")
    return _to_unified(out)


# ─────────────────────────────────────────────────────────────────────────────
# Dataset 3: credit_score — monthly financial snapshots (100k customers)
# Schema: Customer_ID, Month, Annual_Income, Monthly_Inhand_Salary,
#         Num_Bank_Accounts, Outstanding_Debt, Monthly_Balance, Credit_Score
# ─────────────────────────────────────────────────────────────────────────────

def load_credit_score(max_rows: int = 80_000) -> Optional[pd.DataFrame]:
    f = _find_csv("credit_score")
    if f is None:
        log.warning("credit_score CSV not found")
        return None
    log.info(f"  Loading credit_score: {f.name} ({f.stat().st_size // 1_048_576}MB)")
    df = pd.read_csv(f, nrows=max_rows, low_memory=False)

    month_map = {
        "January":1,"February":2,"March":3,"April":4,"May":5,"June":6,
        "July":7,"August":8,"September":9,"October":10,"November":11,"December":12
    }
    df["_m"]  = df.get("Month", "January").map(month_map).fillna(1).astype(int)
    df["_ym"] = df["_m"].apply(lambda m: f"2023-{m:02d}")
    df["_uid"] = df.get("Customer_ID", df.index).astype(str).apply(lambda x: f"cs_{hash(x) % 30_000}")

    rows = []
    for _, row in df.iterrows():
        uid = row["_uid"]
        ym  = row["_ym"]
        salary = pd.to_numeric(row.get("Monthly_Inhand_Salary", 0), errors="coerce") or 0
        debt   = pd.to_numeric(row.get("Outstanding_Debt", 0), errors="coerce") or 0
        balance = pd.to_numeric(row.get("Monthly_Balance", 0), errors="coerce") or 0

        if salary > 0:
            rows.append({"user_id": uid, "year_month": ym,
                         "amount": float(salary), "type": "income", "category": "Salary"})
        if debt > 0:
            debt_monthly = debt / 12
            rows.append({"user_id": uid, "year_month": ym,
                         "amount": float(debt_monthly), "type": "expense", "category": "Debt Payment"})
        if salary > 0:
            # Infer living expenses: salary - balance (what was consumed)
            living = max(salary - balance, salary * 0.3)
            rows.append({"user_id": uid, "year_month": ym,
                         "amount": float(living), "type": "expense", "category": "Living"})

    out = pd.DataFrame(rows)
    log.info(f"    → {len(out):,} rows")
    return _to_unified(out) if len(out) > 0 else None


# ─────────────────────────────────────────────────────────────────────────────
# Dataset 4: credit_fraud (European CC — PCA transformed)
# Schema: Time, V1..V28, Amount, Class
# Use Amount + Time to derive spending patterns (no categories available)
# ─────────────────────────────────────────────────────────────────────────────

def load_credit_fraud(max_rows: int = 50_000) -> Optional[pd.DataFrame]:
    f = _find_csv("credit_fraud")
    if f is None:
        log.warning("credit_fraud CSV not found")
        return None
    log.info(f"  Loading credit_fraud: {f.name} ({f.stat().st_size // 1_048_576}MB)")
    df = pd.read_csv(f, nrows=max_rows, low_memory=False)

    # Time is seconds since first transaction (2-day period)
    df["_time"] = pd.to_numeric(df.get("Time", 0), errors="coerce").fillna(0)
    # Map to fake months (simulate monthly repeat users)
    df["_uid"]  = pd.Series(df.index % 5_000, index=df.index).apply(lambda x: f"eu_{x}")
    df["_ym"]   = (df["_time"] // 86400 % 30).apply(lambda d: f"2024-{(int(d)//5)+1:02d}").clip(upper="2024-06")
    df["_amt"]  = pd.to_numeric(df.get("Amount", 0), errors="coerce").abs()
    df["_type"] = "expense"
    df["_cat"]  = "Card Spend"

    out = df[["_uid","_ym","_amt","_type","_cat"]].copy()
    out.columns = ["user_id","year_month","amount","type","category"]
    log.info(f"    → {len(out):,} rows")
    return _to_unified(out)


# ─────────────────────────────────────────────────────────────────────────────
# Dataset 5: expense_classification — real personal finance (India, 2023-2024)
# Schema: Date, title, category, account, amount, currency, type
# 1,156 granular daily transactions — Food & Drinks, Transport, Bills & Fees etc.
# This is the CLOSEST dataset to ByteWallet transaction structure.
# ─────────────────────────────────────────────────────────────────────────────

def load_expense_classification() -> Optional[pd.DataFrame]:
    f = _find_csv("expense_classification")
    if f is None:
        log.warning("expense_classification CSV not found")
        return None
    log.info(f"  Loading expense_classification: {f.name} ({f.stat().st_size // 1024}KB)")
    df = pd.read_csv(f, low_memory=False)

    # Parse datetime — format: 2024-08-11 13:56:59.652
    df["_date"] = pd.to_datetime(df["Date"], errors="coerce")
    df          = df.dropna(subset=["_date"])
    df["_ym"]   = df["_date"].dt.to_period("M").astype(str)

    # Single user dataset — assign a unique persistent user ID
    df["_uid"]  = "ec_user_001"

    # Amount: some values use "1,234.00" format (commas as thousands sep)
    df["_amt"]  = (
        df["amount"]
        .astype(str)
        .str.replace(",", "", regex=False)
        .pipe(pd.to_numeric, errors="coerce")
        .abs()
    )

    # Type: EXPENSE, INCOME, TRANSFER
    type_map = {"EXPENSE": "expense", "INCOME": "income", "TRANSFER": "transfer"}
    df["_type"] = df["type"].str.upper().map(type_map).fillna("expense")

    # Category mapping to our standard buckets
    cat_map = {
        "Food & Drinks":  "Food",
        "Transport":      "Transport",
        "Bills & Fees":   "Bills",
        "Shopping":       "Shopping",
        "Health":         "Health",
    }
    df["_cat"] = df["category"].map(cat_map).fillna("Other")

    # Exclude zero-amount transfers  
    df = df[df["_amt"] > 0].copy()

    out = df[["_uid","_ym","_amt","_type","_cat"]].copy()
    out.columns = ["user_id","year_month","amount","type","category"]
    log.info(f"    → {len(out):,} rows  (real ASEAN-adjacent personal finance)")
    return _to_unified(out)


# ─────────────────────────────────────────────────────────────────────────────
# Dataset 6: User Provided — personal_expense_classification.csv
# 100 rows of very clean merchant data (Amazon, Starbucks, Netflix etc)
# ─────────────────────────────────────────────────────────────────────────────

def load_user_personal_expense() -> Optional[pd.DataFrame]:
    f = _find_csv("user_personal_expense")
    if f is None:
        return None
    log.info(f"  Loading User CSV: {f.name}")
    df = pd.read_csv(f)
    
    # 100 rows, distribute them evenly across 3 months for a single fake user
    df["_uid"] = "user_desktop_csv"
    
    # Assign random months
    np.random.seed(42)
    month_choices = ["2024-01", "2024-02", "2024-03"]
    df["_ym"] = np.random.choice(month_choices, size=len(df))
    
    df["_amt"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    df["_type"] = "expense"
    
    # Map categories
    cat_map = {
        "food": "Food",
        "shopping": "Shopping",
        "transport": "Transport",
        "entertainment": "Entertainment",
        "technology": "Shopping" 
    }
    df["_cat"] = df["category"].str.lower().map(cat_map).fillna("Other")
    
    out = df[["_uid","_ym","_amt","_type","_cat"]].copy()
    out.columns = ["user_id","year_month","amount","type","category"]
    log.info(f"    → {len(out):,} rows  (manual user load)")
    return _to_unified(out)


# ─────────────────────────────────────────────────────────────────────────────
# Dataset 7: Gen Z Spending (1,700 users x 15 columns)
# ─────────────────────────────────────────────────────────────────────────────

def load_genz_spending() -> Optional[pd.DataFrame]:
    f = _find_csv("genz_spending")
    if f is None:
        return None
    log.info(f"  Loading genz_spending: {f.name}")
    df = pd.read_csv(f)
    
    rows = []
    for _, row in df.iterrows():
        uid = f"genz_{row.get('ID', hash(str(row.values)))}"
        ym = "2024-03" # Treat as a single monthly snapshot
        
        inc = pd.to_numeric(row.get("Income (USD)", 0), errors="coerce")
        if pd.notna(inc) and inc > 0:
            rows.append((uid, ym, inc, "income", "Salary"))
            
        expense_map = {
            "Rent (USD)": "Rent",
            "Groceries (USD)": "Food",
            "Eating Out (USD)": "Food",
            "Entertainment (USD)": "Entertainment",
            "Subscription Services (USD)": "Bills",
            "Education (USD)": "Education",
            "Online Shopping (USD)": "Shopping",
            "Travel (USD)": "Transport",
            "Fitness (USD)": "Health",
            "Miscellaneous (USD)": "Other"
        }
        
        for col, cat in expense_map.items():
            amt = pd.to_numeric(row.get(col, 0), errors="coerce")
            if pd.notna(amt) and amt > 0:
                rows.append((uid, ym, amt, "expense", cat))
                
    out = pd.DataFrame(rows, columns=["user_id", "year_month", "amount", "type", "category"])
    log.info(f"    → {len(out):,} rows (flattened metrics)")
    return _to_unified(out)


# ─────────────────────────────────────────────────────────────────────────────
# Master loader
# ─────────────────────────────────────────────────────────────────────────────

def load_all_kaggle() -> pd.DataFrame:
    """
    Load all available Kaggle datasets, unify schema, return combined DataFrame.
    Gracefully skips missing datasets.

    Returns DataFrame with columns:
        user_id, year_month, amount, type, category
    """
    log.info("\nLoading Kaggle & Extra datasets...")

    loaders = [
        ("credit_transactions",    load_credit_transactions),
        ("online_fraud",           load_online_fraud),
        ("credit_score",           load_credit_score),
        ("credit_fraud",           load_credit_fraud),
        ("expense_classification", load_expense_classification),
        ("user_personal_expense",  load_user_personal_expense),
        ("genz_spending",          load_genz_spending),
    ]

    frames = []
    for name, loader in loaders:
        try:
            df = loader()
            if df is not None and len(df) > 0:
                df["_source"] = name
                frames.append(df)
                log.info(f"  {name}: {len(df):,} unified rows")
        except Exception as e:
            log.warning(f"  {name} failed: {e}")

    if not frames:
        log.warning("  No Kaggle datasets loaded — only real CSV data will be used")
        return pd.DataFrame(columns=["user_id","year_month","amount","type","category"])

    combined = pd.concat([f.drop(columns=["_source"], errors="ignore") for f in frames],
                         ignore_index=True)
    combined["amount"] = pd.to_numeric(combined["amount"], errors="coerce").fillna(0)
    combined = combined[combined["amount"] > 0]

    log.info(f"\nKaggle total: {len(combined):,} rows from {len(frames)} datasets")
    log.info(f"   type dist: {combined['type'].value_counts().to_dict()}")
    log.info(f"   top categories: {combined['category'].value_counts().head(8).to_dict()}")
    return combined


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    df = load_all_kaggle()
    print(f"\nFinal shape: {df.shape}")
    print(df["type"].value_counts())
    print(df["category"].value_counts().head(10))
