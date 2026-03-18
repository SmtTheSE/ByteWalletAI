"""
scripts/download_kaggle_datasets.py

Downloads all 8 selected Kaggle datasets for ByteWallet AI model training.
Requires a Kaggle API token (~/.kaggle/kaggle.json or KAGGLE_USERNAME/KAGGLE_KEY env vars).

Usage:
    python scripts/download_kaggle_datasets.py

Datasets downloaded into:  data/kaggle/<dataset-slug>/
"""
import os
import sys
from pathlib import Path

try:
    from kaggle.api.kaggle_api_extended import KaggleApi
except ImportError:
    print("ERROR: kaggle package not installed. Run: pip install kaggle")
    sys.exit(1)

KAGGLE_BASE = Path(__file__).parent.parent / "data" / "kaggle"
KAGGLE_BASE.mkdir(parents=True, exist_ok=True)

# List of (owner/dataset-slug, description, purpose)
DATASETS = [
    ("arjunbhasin2013/personal-finance-tracker-dataset",
     "Personal Finance Tracker (3 000 users × multi-year monthly snapshots)",
     "Core burn-rate label training"),

    ("bhadramohit/gen-z-money-spending-dataset",
     "Gen Z Money Spending (1 700 records, 15 attributes)",
     "Youth spending category distribution"),

    ("mathchi/budgetwise-personal-finance-dataset",
     "BudgetWise Personal Finance (15 000+ transactions, 2021-2024)",
     "Transaction classification, overspend labelling"),

    ("joeyhahaha/personal-budget-transactions",
     "Personal Budget Transactions (Jul 2022 – Mar 2025)",
     "Most recent date range, category patterns"),

    ("sumanthnimmagadda/student-spending-habits-dataset",
     "Student Spending Habits (1 000 college students)",
     "Youth segment modeling"),

    ("kartik2112/fraud-detection",
     "Financial Fraud Detection (large synthetic transactions)",
     "Risk / scam pattern features"),

    ("fatihilhan/personal-expense-classification",
     "Personal Expense Classification",
     "Category standardisation NLP"),

    ("shreyasur965/personal-finance-ml-dataset",
     "Personal Finance ML Dataset (32 424 records, Jan 2020 – Jul 2024)",
     "Financial health segmentation"),
]


def download_all(force: bool = False):
    api = KaggleApi()
    api.authenticate()

    for slug, description, purpose in DATASETS:
        owner, name = slug.split("/")
        dest = KAGGLE_BASE / name
        dest.mkdir(exist_ok=True)

        # Skip if already downloaded (check for any CSV inside)
        existing_csvs = list(dest.glob("*.csv"))
        if existing_csvs and not force:
            print(f"  [SKIP] {name} — already downloaded ({len(existing_csvs)} CSV file(s))")
            continue

        print(f"\n→ Downloading: {description}")
        print(f"  Purpose: {purpose}")
        print(f"  Destination: {dest}")
        try:
            api.dataset_download_files(
                dataset=slug,
                path=str(dest),
                unzip=True,
                quiet=False,
            )
            csvs = list(dest.glob("*.csv"))
            print(f"  ✓ Done — {len(csvs)} CSV file(s): {[c.name for c in csvs]}")
        except Exception as e:
            print(f"  ✗ Failed to download {slug}: {e}")

    print("\n✅ All downloads complete. Files in:", KAGGLE_BASE)


if __name__ == "__main__":
    force = "--force" in sys.argv
    download_all(force=force)
