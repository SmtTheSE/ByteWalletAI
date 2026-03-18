"""
ml/load_real_data.py
Load and clean the three real ByteWallet CSV exports.

Outputs:
    users_df      - users table
    tx_df         - transactions table (cleaned, typed)
    friends_df    - friends table
"""
from pathlib import Path
import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data"


def load_users(path: Path = DATA_DIR / "users_rows.csv") -> pd.DataFrame:
    df = pd.read_csv(path)
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True, errors="coerce")
    df["updated_at"] = pd.to_datetime(df["updated_at"], utc=True, errors="coerce")
    df["last_seen"]  = pd.to_datetime(df["last_seen"],  utc=True, errors="coerce")
    df["balance_banking"] = pd.to_numeric(df["balance_banking"], errors="coerce").fillna(0)
    df["balance_cash"]    = pd.to_numeric(df["balance_cash"],    errors="coerce").fillna(0)
    df["balance_total"]   = df["balance_banking"] + df["balance_cash"]
    return df


def load_transactions(path: Path = DATA_DIR / "transactions_rows.csv") -> pd.DataFrame:
    df = pd.read_csv(path)

    # Parse timestamps (timezone-aware)
    df["timestamp"]  = pd.to_datetime(df["timestamp"],  utc=True, errors="coerce")
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True, errors="coerce")

    # Ensure amount is positive numeric
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").abs().fillna(0)

    # Normalise transaction type to lowercase
    df["type"] = df["type"].str.strip().str.lower()
    # Map any non-standard types to our three canonical values
    type_map = {
        "expense": "expense",
        "income":  "income",
        "transfer": "transfer",
    }
    df["type"] = df["type"].map(type_map).fillna("expense")

    # Normalise category
    df["category"] = df["category"].str.strip().fillna("Other")

    # Add helper date columns for feature engineering
    df["year"]       = df["timestamp"].dt.year
    df["month"]      = df["timestamp"].dt.month
    df["day"]        = df["timestamp"].dt.day
    df["year_month"] = df["timestamp"].dt.to_period("M")

    return df


def load_friends(path: Path = DATA_DIR / "friends_rows.csv") -> pd.DataFrame:
    df = pd.read_csv(path)
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True, errors="coerce")
    df["updated_at"] = pd.to_datetime(df["updated_at"], utc=True, errors="coerce")
    return df


def load_all():
    """Convenience function — returns (users_df, tx_df, friends_df)."""
    return load_users(), load_transactions(), load_friends()


if __name__ == "__main__":
    users, tx, friends = load_all()
    print(f"Users:        {len(users)} rows")
    print(f"Transactions: {len(tx)} rows | types: {tx['type'].value_counts().to_dict()}")
    print(f"Friends:      {len(friends)} rows")
    print("\nTransaction categories:\n", tx["category"].value_counts())
