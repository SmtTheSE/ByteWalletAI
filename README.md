# ByteWallet AI

> **AI-powered financial burn-rate prediction for ASEAN youth.**
> Custom ML model --- privacy-first, purely on-device mathematical predictions.

---

ByteWallet AI exposes a hybrid API with both predictive math and generative AI:

```
POST /v1/predict-burn-rate
```
The core hybrid endpoint. Combines **Custom ML Inference** with **Local LLM (Ollama)** voice generation, and rigidly incorporates **Frontend-calculated Heuristic Flags (Logic 1 & 2)**. Calculates `risk_level`, numeric projections, and a hyper-personalized coaching message completely offline driven by the factual frontend triggers.

```
POST /v1/federated/submit-update
```
**Phase 5 Federated Learning:** On-device training simulator that submits gradient weight deltas to the central server without exposing raw transaction data.

---

## Architecture (Hybrid AI)

```
Wallet Frontend
      
        POST /v1/predict-burn-rate

  FastAPI App (app/)             
                                 
  1. Hybrid Input   Frontend calculates Logic 1 (Shortfall) and 
                    Logic 2 (Mid-Month Check) mathematically and 
                    passes them as deterministic signal flags.
                    
  2. ML Service   Custom GradientBoostingClassifier
     (ml/inference_core.py)       trained on:
                                  • Real ByteWallet CSV data (85 real txns)
                                  • Kaggle financial datasets (8 datasets)
                                  • Synthetic ASEAN youth data
                                                           
  3. Rules Service  Adaptive AI Risk Engine
     (app/services/rules.py)
                                                           
  4. Messaging Service  Adaptive Generative Engine
     (app/services/messaging_service.py) Integrates the rigid frontend signals 
                                         to generate 0-hallucination coaching.
                                                           
  5. Response assembled & returned to frontend             
-
```

## Advanced Intelligence Architecture (Phases 1-5)

In addition to the core ML predictor, ByteWallet AI implements a 5-phase intelligence upgrade:

1. **Phase 1: Local Hybrid Architecture (ML + Ollama Voice)** --- Automatically routes high-risk findings from the Custom ML model to a local **Ollama** instance. Includes an **Adaptive Regex Engine** (10s fallback) for hyper-personalized coaching without an LLM.
2. **Phase 2: RAG on Transactions** --- Uses a local ChromaDB vector store to embed user transaction history, providing personalized context to the generative engine.
3. **Phase 3: Hyper-Granular Enrichment** --- Enriches raw transactions with temporal (payday week), spatial (CBD buckets), and behavioral (impulse score, recurrence) features for both RAG and ML.
4. **Phase 4: Proactive Multi-Agent Reasoning** --- An orchestration layer running 6 specialized agents: Liquidity (Condition-1), Income, Goal, Subscription, Anomaly, and Savings.
5. **Phase 5: Federated Learning (Edge AI)** --- A `FedAvg` local server combined with a client simulator that trains the models on-device and transmits only mathematical weight deltas to protect privacy.

---

## One-Click Cloud Deployment
ByteWallet AI is pre-configured for **Render**. Use the `render.yaml` file to deploy as a Blueprint. See [DEPLOYMENT_GUIDE_RENDER.md](file:///Users/sittminthar/Desktop/AI%20YOUTH%20INC/bytewallet_ai/docs/DEPLOYMENT_GUIDE_RENDER.md) for details.

---

## Local Installation

### 1. Install dependencies

```bash
cd bytewallet_ai
pip install -r requirements.txt
```

### 2. Train the custom ML model

```bash
python -m ml.train_model
```

This will:
- Load real `data/users_rows.csv` + `data/transactions_rows.csv`
- Load any Kaggle datasets in `data/kaggle/` (if downloaded)
- Generate synthetic ASEAN youth data to augment training
- Train a `GradientBoostingClassifier`
- Save `models/burn_rate_model.pkl` + `models/feature_config.json`



```bash
uvicorn app.main:app --reload --port 8000
```

Open: http://localhost:8000/docs --- Swagger UI with live testing.

---

## Example Request

```bash
curl -X POST http://localhost:8000/v1/predict-burn-rate \
  -H "Content-Type: application/json" \
  -d @tests/sample_kukue_request.json
```

**Sample Response (with Logic Alignment):**

```json
{
  "user_id": "717d7cec-...",
  "currency": "VND",
  "risk_level": "high",
  "shortfall_prob": 0.83,
  "predicted_total_spend": 2750000,
  "predicted_month_end_balance": -1500000,
  "budget_total": 3000000,
  "budget_overshoot_amount": 345000,
  "budget_overshoot_percent": 0.115,
  "user_context": {
    "total_balance": 5000000,
    "essential_expenses": 2000000,
    "discretionary_baseline": 3000000
  },
  "logic_signals": {
    "shortfall_detected": true,
    "shortfall_amount": 500000,
    "mid_month_alert": true,
    "usage_percentage": 0.68
  },
  "recommendation_engine": {
    "target_category": "Food",
    "avg_cost_per_instance": 22900,
    "required_avoidance_count": 22
  },
  "trigger_rule": "15th_65_percent",
  "trigger_rule_flags": {
    "day_fraction": 0.58,
    "budget_used_percent": 0.68,
    "hit_15th_65_percent_rule": true
  },
  "top_risky_categories": [
    {
      "category": "Food",
      "current_spent": 229000,
      "avg_spent_last_3_months": 183200,
      "projected_spent": 396000
    }
  ],
  "ai_message": "Hey Ku Kue, you've already used 68% of your budget halfway through the month --- things are tight! Avoid spending on Food 22 times this month to cover your predicted shortfall of 500,000 VND.",
  "ai_mode_used": "rules_only",
  "generated_at": "2026-03-18T13:00:00Z"
}
```

---

## Kaggle Datasets (Download for Better Training)

```bash
# Set up Kaggle API key first:
# 1. Go to https://www.kaggle.com/settings → API → Create New Token
# 2. Save ~/.kaggle/kaggle.json

python scripts/download_kaggle_datasets.py
```

| Dataset | Purpose |
|---------|---------|
| Personal Finance Tracker (3,000 users) | Core burn-rate training |
| Gen Z Money Spending (1,700 records) | Youth spending patterns |
| BudgetWise (15,000+ transactions) | Transaction classification |
| Personal Budget Transactions (2022–2025) | Most recent patterns |
| Student Spending Habits (1,000 students) | Youth segment modeling |
| Financial Fraud Detection | Risk pattern features |
| Personal Expense Classification | Category standardisation |
| Personal Finance ML Dataset (32,424 records) | Financial health segmentation |
| Vietnamese MoMo e-Wallet (13,000+ records) | Authentic Vietnamese mobile top-ups and telecommunication bills |

---

## Project Structure

```
bytewallet_ai/
  app/
    main.py                  # FastAPI app + CORS + lifespan
    api.py                   # POST /v1/predict-burn-rate route
    schemas.py               # Pydantic request / response models
    config.py                # Environment variable settings
    services/
      ml_service.py          # Model loading + prediction wrapper
      messaging_service.py   # Rules Engine integration
      rules.py               # 15th/65% business rule
  ml/
    load_real_data.py        # Load ByteWallet CSVs
    load_kaggle_data.py      # Load + normalise Kaggle datasets
    labeler.py               # Shortfall event label derivation
    features.py              # Feature engineering
    train_model.py           # Training script → models/*.pkl
    inference_core.py        # Core prediction logic
  scripts/
    download_kaggle_datasets.py  # Auto-download 8 Kaggle datasets
  data/
    users_rows.csv           # Real ByteWallet users
    transactions_rows.csv    # Real ByteWallet transactions
    friends_rows.csv         # Real ByteWallet friends
    kaggle/                  # Auto-downloaded Kaggle datasets
  models/                    # Saved model artifacts
  docs/
    AI_TECHNICAL_WHITEPAPER.md     # Deep dive into ML metrics & architecture
    ByteWallet_AI_Proposal.docx    # Official grant proposal
    Frontend_Integration_Guide.md  # How to consume the API & Webhooks
  tests/
    test_api.py              # API integration tests
    test_ml.py               # ML unit tests
    sample_kukue_request.json
  README.md
  requirements.txt
  Dockerfile
  .env.example
```

---

## Running Tests

```bash
cd bytewallet_ai
python -m pytest tests/ -v
```

---

## AI Ready ASEAN Youth Challenge --- Alignment

| Focus Area | How ByteWallet AI addresses it |
|------------|-------------------------------|
| **Knowledge, Skills & Learning** | Financial literacy through everyday AI nudges, not classroom lectures |
| **Stronger Communities** | Shared budgeting culture, reduced scam vulnerability, peer savings challenges |
| **SDG 1 --- No Poverty** | Early-warning system that prevents youth from falling into debt cycles |
| **SDG 4 --- Quality Education** | Integrable into school financial literacy programs ("trainer mode") |
| **SDG 8 --- Decent Work** | Helps youth build saving habits needed to invest in skills/education |

**Privacy:** All inference runs mathematically on-device without cloud computation. No financial data leaves the framework.

**Responsible AI:** Model is explainable (feature importance), rule-based fallback always works, no black-box decisions.

---

## Docker

```bash
docker build -t bytewallet-ai .
docker run -p 8000:8000 -v $(pwd)/data:/app/data bytewallet-ai
```
