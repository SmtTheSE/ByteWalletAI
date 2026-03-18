"""
ml/train_model.py  (PRODUCTION VERSION v2)

Training pipeline for ByteWallet AI Burn-Rate Model.

Data sources (in priority order):
  1. Real ByteWallet CSVs       — users_rows.csv, transactions_rows.csv
  2. Real Kaggle datasets       — credit_transactions, online_fraud, credit_score, credit_fraud
  3. Synthetic ASEAN youth data — generated to augment real data and balance classes

Model: GradientBoostingClassifier (scikit-learn)
  - Chosen for: interpretability, no GPU needed, excellent on tabular data
  - Wrapped in a full sklearn Pipeline (imputer → scaler → classifier)

Output artifacts:
  models/burn_rate_model.pkl      — full sklearn pipeline
  models/feature_config.json      — metadata + feature importance

Run:
    cd bytewallet_ai
    python -m ml.train_model
"""
from __future__ import annotations
import json
import logging
import sys
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    classification_report, roc_auc_score,
    precision_recall_fscore_support, confusion_matrix,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.utils import resample

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("train_model")

ROOT        = Path(__file__).parent.parent
MODELS_DIR  = ROOT / "models"
MODELS_DIR.mkdir(exist_ok=True)
MODEL_PATH  = MODELS_DIR / "burn_rate_model.pkl"
CFG_PATH    = MODELS_DIR / "feature_config.json"

sys.path.insert(0, str(ROOT))

from ml.load_real_data   import load_transactions
from ml.load_kaggle_data import load_all_kaggle
from ml.labeler          import build_labelled_dataset, compute_monthly_totals
from ml.features         import build_training_features, FEATURE_COLUMNS


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic ASEAN youth data generator
# ─────────────────────────────────────────────────────────────────────────────

def generate_asean_synthetic(n_users: int = 200, months_per_user: int = 6) -> pd.DataFrame:
    """
    Generate realistic synthetic transaction data modelled on ASEAN youth patterns.
    Currency scale: Vietnamese Dong (VND). 10,000 VND ≈ $0.40 USD.

    Profiles:
      - Student     (low income ~2-4M VND/month, high food/transport spend)
      - GigWorker   (irregular income ~4-8M, lumpy patterns)
      - YoungPro    (stable income ~8-15M, growing discretionary spend)
      - Scarcity    (income barely covers rent, high shortfall probability)
    """
    rng = np.random.default_rng(42)
    PROFILES = [
        # (name, income_range,        expense_to_income, categories_weights)
        ("Student",   (2_000_000,  5_000_000),  0.85,
         {"Food":0.35,"Transport":0.20,"Shopping":0.20,"Entertainment":0.10,"Health":0.05,"Other":0.10}),
        ("GigWorker", (3_000_000,  8_000_000),  0.75,
         {"Food":0.30,"Transport":0.25,"Shopping":0.15,"Health":0.10,"Rent":0.15,"Other":0.05}),
        ("YoungPro",  (8_000_000, 15_000_000),  0.65,
         {"Food":0.25,"Transport":0.15,"Shopping":0.30,"Health":0.10,"Rent":0.15,"Entertainment":0.05}),
        ("Scarcity",  (1_500_000,  3_000_000),  1.05,   # consistently over-spending
         {"Food":0.40,"Transport":0.20,"Rent":0.25,"Health":0.08,"Other":0.07}),
    ]

    records = []
    for uid in range(n_users):
        profile_name, income_range, expense_ratio, cat_weights = PROFILES[uid % len(PROFILES)]
        cats      = list(cat_weights.keys())
        cat_probs = list(cat_weights.values())

        base_income = rng.integers(income_range[0], income_range[1])

        for month_offset in range(months_per_user):
            year  = 2024 + (month_offset // 12)
            month = (month_offset % 12) + 1
            ym    = f"{year:04d}-{month:02d}"

            # Income (may be irregular for GigWorker)
            if profile_name == "GigWorker" and rng.random() < 0.4:
                income = base_income * rng.uniform(0.3, 1.8)
            else:
                income = base_income * rng.uniform(0.9, 1.1)

            records.append({
                "user_id": f"synth_{uid}",
                "year_month": ym, "day": 1,
                "amount": float(income),
                "type": "income", "category": "Salary",
            })

            # Expense transactions (8–35 per month)
            total_budget = income * expense_ratio
            n_txns = int(rng.integers(8, 35))
            spent  = 0.0
            for _ in range(n_txns):
                if spent >= total_budget * 1.2:
                    break
                cat = rng.choice(cats, p=cat_probs)
                # Category-specific amount ranges (VND)
                cat_max = {
                    "Food":700_000, "Transport":250_000, "Shopping":1_500_000,
                    "Entertainment":800_000, "Health":500_000, "Rent":3_000_000,
                    "Debt Payment":1_000_000, "Other":400_000,
                }
                max_amt = cat_max.get(cat, 500_000)
                amt = float(rng.integers(15_000, max(15_001, max_amt)))
                day = int(rng.integers(1, 29))
                records.append({
                    "user_id": f"synth_{uid}",
                    "year_month": ym, "day": day,
                    "amount": amt,
                    "type": "expense", "category": cat,
                })
                spent += amt

    return pd.DataFrame(records)


# ─────────────────────────────────────────────────────────────────────────────
# Kaggle → transaction row adapter
# ─────────────────────────────────────────────────────────────────────────────

def adapt_kaggle_to_tx(kaggle_df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert the unified Kaggle DataFrame (user_id, year_month, amount, type, category)
    to the transaction-row format used by labeler + features
    (adds day=15 approximation).
    """
    df = kaggle_df.copy()
    df["day"] = 15    # mid-month approximation
    df = df[["user_id", "year_month", "day", "amount", "type", "category"]].copy()
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    df = df[df["amount"] > 0]
    # Normalise year_month
    df["year_month"] = df["year_month"].astype(str).str[:7]
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Balance classes via oversampling minority
# ─────────────────────────────────────────────────────────────────────────────

def balance_classes(X: pd.DataFrame, y: pd.Series) -> tuple[pd.DataFrame, pd.Series]:
    """Oversample the minority class so training sees balanced examples."""
    df = X.copy()
    df["__label__"] = y.values
    majority = df[df["__label__"] == 0]
    minority = df[df["__label__"] == 1]
    if len(minority) == 0 or len(majority) == 0:
        return X, y
    target_n = max(len(majority), len(minority))
    minority_up = resample(minority, replace=True, n_samples=target_n, random_state=42)
    balanced = pd.concat([majority, minority_up]).sample(frac=1, random_state=42)
    return balanced.drop("__label__", axis=1), balanced["__label__"]


# ─────────────────────────────────────────────────────────────────────────────
# Main training pipeline
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("╔══════════════════════════════════════════════════╗")
    log.info("║   ByteWallet AI — Production Model Training      ║")
    log.info("╚══════════════════════════════════════════════════╝")

    # ── 1. Load real data ─────────────────────────────────────────────────────
    log.info("\n[1/6] Loading real ByteWallet data…")
    real_tx = load_transactions()
    log.info(f"      Real rows: {len(real_tx):,}  |  types: {real_tx['type'].value_counts().to_dict()}")

    # ── 2. Load Kaggle data ───────────────────────────────────────────────────
    log.info("\n[2/6] Loading Kaggle datasets…")
    kaggle_unified = load_all_kaggle()
    kaggle_tx      = adapt_kaggle_to_tx(kaggle_unified)
    log.info(f"      Kaggle rows: {len(kaggle_tx):,}")

    # ── 3. Generate synthetic ASEAN data ──────────────────────────────────────
    log.info("\n[3/6] Generating synthetic ASEAN youth data…")
    synth_tx = generate_asean_synthetic(n_users=300, months_per_user=8)
    log.info(f"      Synthetic rows: {len(synth_tx):,}")

    # ── 4. Combine all sources ────────────────────────────────────────────────
    log.info("\n[4/6] Combining all data sources…")
    all_cols = ["user_id", "year_month", "day", "amount", "type", "category"]

    real_sub = real_tx[all_cols].copy()
    real_sub["year_month"] = real_tx["year_month"].astype(str)

    all_tx = pd.concat([real_sub, kaggle_tx, synth_tx[all_cols]], ignore_index=True)
    all_tx["amount"]     = pd.to_numeric(all_tx["amount"], errors="coerce").fillna(0)
    all_tx["day"]        = pd.to_numeric(all_tx["day"],    errors="coerce").fillna(15).astype(int).clip(1, 31)
    all_tx["year_month"] = all_tx["year_month"].astype(str).str[:7]
    
    # Filter valid amounts and valid YYYY-MM dates
    all_tx = all_tx[
        (all_tx["amount"] > 0) & 
        (all_tx["year_month"].str.match(r"^\d{4}-\d{2}$", na=False))
    ].copy()

    log.info(f"      Total: {len(all_tx):,} rows")
    log.info(f"      Sources: real={len(real_sub):,}  kaggle={len(kaggle_tx):,}  synthetic={len(synth_tx):,}")
    log.info(f"      Type dist: {all_tx['type'].value_counts().to_dict()}")
    log.info(f"      Unique users: {all_tx['user_id'].nunique():,}")

    # ── 5. Build labels + features ────────────────────────────────────────────
    log.info("\n[5/6] Building labels and feature matrix…")
    labels   = build_labelled_dataset(all_tx)
    train_df = build_training_features(all_tx, labels, snapshot_day=15)

    log.info(f"      Labelled months: {len(labels):,}")
    log.info(f"      Shortfall rate:  {labels['shortfall_event'].mean():.1%}")
    log.info(f"      Feature rows:    {len(train_df):,}")

    if len(train_df) < 20:
        log.warning("Too few rows — extending synthetic data")
        synth_extra = generate_asean_synthetic(n_users=500, months_per_user=12)
        all_tx2   = pd.concat([all_tx, synth_extra[all_cols]], ignore_index=True)
        labels    = build_labelled_dataset(all_tx2)
        train_df  = build_training_features(all_tx2, labels, snapshot_day=15)

    X = train_df[FEATURE_COLUMNS].fillna(0).astype(float)
    y = train_df["shortfall_event"].astype(int)

    log.info(f"      Class balance before resampling: {y.value_counts().to_dict()}")

    # Balance classes
    X_bal, y_bal = balance_classes(X, y)
    log.info(f"      Class balance after  resampling: {y_bal.value_counts().to_dict()}")

    # ── 6. Train + evaluate ───────────────────────────────────────────────────
    log.info("\n[6/6] Training model…")

    # Train/test split (stratified)
    if len(X_bal) >= 40:
        X_train, X_test, y_train, y_test = train_test_split(
            X_bal, y_bal, test_size=0.2, random_state=42, stratify=y_bal
        )
    else:
        X_train, X_test, y_train, y_test = X_bal, X_bal, y_bal, y_bal

    model = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler",  StandardScaler()),
        ("clf", GradientBoostingClassifier(
            n_estimators=300,
            learning_rate=0.07,
            max_depth=4,
            min_samples_split=10,
            subsample=0.85,
            max_features="sqrt",
            random_state=42,
        )),
    ])
    model.fit(X_train, y_train)

    # Evaluate
    y_prob = model.predict_proba(X_test)[:, 1]
    y_pred = model.predict(X_test)

    prec, rec, f1, _ = precision_recall_fscore_support(y_test, y_pred, average="weighted")
    auc  = roc_auc_score(y_test, y_prob) if len(set(y_test)) > 1 else 0.0
    cm   = confusion_matrix(y_test, y_pred)

    log.info("\n" + "─"*50)
    log.info("CLASSIFICATION REPORT:")
    log.info("\n" + classification_report(y_test, y_pred, target_names=["no_shortfall","shortfall"]))
    log.info(f"ROC-AUC:   {auc:.4f}")
    log.info(f"F1 Score:  {f1:.4f}")
    log.info(f"Confusion Matrix:\n{cm}")

    # Cross-validation on full balanced data
    if len(X_bal) >= 50:
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        cv_scores = cross_val_score(model, X_bal, y_bal, cv=cv, scoring="roc_auc", n_jobs=-1)
        log.info(f"5-Fold CV ROC-AUC: {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")

    # Feature importance
    clf          = model.named_steps["clf"]
    importances  = clf.feature_importances_
    feat_imp     = sorted(zip(FEATURE_COLUMNS, importances), key=lambda x: x[1], reverse=True)
    log.info("\nTop 10 Feature Importances:")
    for feat, imp in feat_imp[:10]:
        bar = "█" * int(imp * 40)
        log.info(f"  {feat:<35s} {imp:.4f}  {bar}")

    # ── Save artifacts ─────────────────────────────────────────────────────────
    joblib.dump(model, MODEL_PATH)
    log.info(f"\n✅ Model saved → {MODEL_PATH}")

    config = {
        "feature_columns":    FEATURE_COLUMNS,
        "model_type":         "GradientBoostingClassifier",
        "pipeline_steps":     ["SimpleImputer", "StandardScaler", "GradientBoostingClassifier"],
        "training_rows":      int(len(X_train)),
        "test_rows":          int(len(X_test)),
        "shortfall_rate":     float(y.mean()),
        "roc_auc":            round(float(auc), 4),
        "f1_weighted":        round(float(f1), 4),
        "real_rows":          int(len(real_sub)),
        "kaggle_rows":        int(len(kaggle_tx)),
        "synthetic_rows":     int(len(synth_tx)),
        "feature_importance": {f: float(i) for f, i in feat_imp},
    }
    with open(CFG_PATH, "w") as fh:
        json.dump(config, fh, indent=2)
    log.info(f"✅ Config saved → {CFG_PATH}")
    log.info("\n╔══════════════════════════════════════════════════╗")
    log.info("║   Training complete — model ready for serving    ║")
    log.info("╚══════════════════════════════════════════════════╝")


if __name__ == "__main__":
    main()
