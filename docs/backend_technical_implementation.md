# ByteWallet AI: Backend Technical Implementation Details

This document provides a highly detailed breakdown of the Python codebase implementation for the ByteWallet AI Backend. It explicitly details what each file does, why it exists, and the technical mechanisms used to achieve the **Logical Flow and Frontend Needs** described in the Logic 1 (Shortfall Analysis) and Logic 2 (Mid-Month Check) specs.

---

## 1. Context: Hybrid Integration Strategy
The system shifts away from relying purely on black-box Machine Learning or LLM hallucinations for deciding if a user is facing a financial crisis. Instead, it expects the frontend to execute rigid mathematical formulas (Condition 1 & 2) and pass the results to the backend. The backend's job is to orchestrate these deterministic "Heuristic Flags" alongside statistical Machine Learning to generate high-quality, localized coaching using an LLM.

---

## 2. Core API Layer

### `app/schemas.py`
**What it does**: Defines the Pydantic data schemas for API Requests and Responses (`/v1/predict-burn-rate`). 
**Why it exists**: Pydantic ensures strict type validation on data entering and exiting the Python application. If the frontend sends incorrectly formatted data, Pydantic immediately rejects it with a 422 Unprocessable Entity error.
**Implementation details for Frontend Needs**:
- To perfectly map the Logic 1 & 2 frontend calculations to the API, three classes were added to `schemas.py`: `UserContext`, `LogicSignals`, and `RecommendationEngine`.
- These are attached to the `PredictBurnRateRequest` as *optional* fields. 
- Example mapping: Condition 1 "Needed Amount" is passed into `logic_signals.shortfall_amount`. Condition 2 "Current Balance > 50%" is passed into `logic_signals.mid_month_alert` and `logic_signals.usage_percentage`.

### `app/api.py`
**What it does**: Defines the FastAPI endpoints, acting as the main controller. It orchestrates ML calls, business rule checks, and messaging generation.
**Why it exists**: It routes frontend HTTP traffic to the appropriate Python utility services.
**Implementation details for Frontend Needs**:
- The `/v1/predict-burn-rate` route intercepts the incoming payload.
- **Override Logic**: Instead of running its own mathematical models for shortfall logic unconditionally, `api.py` explicitly checks: `payload.logic_signals if payload.logic_signals else LogicSignals(...)`. If the frontend provides pre-calculated math, the API prioritizes it, cementing the frontend as the absolute "source of truth".
- It bundles these inputs into a final payload sent to `messaging_service.generate_smart_ai_message()`.

---

## 3. The Proactive "Agent" Layer (Fallback Heuristics)

While the frontend calculates the primary heuristic signals, the backend maintains a set of "Agents" designed to act as fallbacks if the frontend fails to send `logic_signals`, or to derive further insights for multi-agent logic tracking.

### `app/agents/liquidity_agent.py`
**What it does**: Contains the backend's internal Python implementation of **Logic 1 (Shortfall Analysis)**. 
**Why it exists**: Acts defensively. If the frontend omits the recommendation parameters, this agent analyzes daily spending limits versus essential obligations.
**Implementation details**:
- Uses `pandas` to aggregate expenses in "less important" categories (`LESS_IMPORTANT_CATEGORIES = {"shopping", "entertainment", "food", "snacks", "coffee", ...}`).
- Determines `projected_balance_in_hand` (Total balance - 30-day projected extra spend).
- Calculates the shortfall and identifies the topmost category to cut, returning an `items_to_cut` integer mathematically identical to the frontend's Condition 1 Spec.

### `app/agents/midmonth_agent.py`
**What it does**: Contains the backend's internal Python implementation of **Logic 2 (Mid-Month Check)**.
**Why it exists**: Fallback for mid-month alert processing. 
**Implementation details**:
- Converts `current_date` to ascertain if it falls between days 14-16.
- Subtracts "Essential Obligations" from "Total Balance" to define an `actual_balance_baseline`.
- If `discretionary_spent / actual_balance_baseline > 0.5`, it throws a severe Warning alert, mirroring the Logic 2 spec's `> 50%` threshold.

---

## 4. Synthesis & Reasoning Layer

### `app/services/messaging_service.py`
**What it does**: Transforms the rigid mathematical data (Logic 1 & 2) and Statistical ML predictions into a human-readable coaching message ("ByteCoach").
**Why it exists**: Users respond better to conversational empathy than raw JSON variables.
**Implementation details for Frontend Needs**:
- The `generate_smart_ai_message()` function takes the `logic_signals` and `recommendation_engine` data extracted out of `api.py`.
- It dynamically crafts a prompt specifically for the local LLM (Ollama): 
  - *Example injected string*: `Logic 1 (Shortfall): YES. Shortfall: 500000 VND. Recommendation: To cover shortfall, avoid 20 Snacks purchases.`
- This tightly bounds the Generative AI. It cannot invent numbers; the prompt mathematically forces the AI coach to repeat the precise numbers calculated by the Frontend.
- If Ollama timeouts (set to a fast 10s cutoff to prevent latency), it drops straight to a **Regex Engine Fallback** (`_get_pattern_advice`), scanning the last 10 transactions to deliver instantaneous hardcoded advice.

---

## 5. Machine Learning "Predictive" Layer

### `ml/inference_core.py`
**What it does**: Runs the custom-trained `GradientBoostingClassifier` to estimate whether the user is heading toward a general burnout (`shortfall_prob`).
**Why it exists**: To predict fluid future behaviour (unlike the deterministic heuristics which check rigid limits).
**Implementation details**:
- Calculates `budget_overshoot_percent` and creates the `top_risky_categories` using `pandas` vectorized logic filtering.
- Provides `risk_level` as an overarching flag (low, medium, high) combined with the heuristic signals.

---

## Summary of the Integration Pipeline

1. **Frontend App** records a transaction.
2. **Frontend App** mathematically calculates: Do we have a Monthly Plan Shortfall? (Logic 1).
3. **Frontend App** mathematically calculates: Is it mid-month and have they spent > 50%? (Logic 2).
4. **Frontend App** sends payload → Python `app/api.py`.
5. **Python `app/schemas.py`** validates the types.
6. **Python `app/api.py`** intercepts the logic flags.
7. **Python `app/services/messaging_service.py`** forces the LLM to spit out a coaching sentence incorporating these exact frontend numbers.
8. **Python `app/api.py`** returns the `PredictBurnRateResponse`.
