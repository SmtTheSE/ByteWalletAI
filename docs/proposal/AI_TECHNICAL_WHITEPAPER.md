# ByteWallet AI: Technical Architecture & Whitepaper (v2.1)
**Author:** Sitt Min Thar

This document serves as the internal technical specification and assessment of the ByteWallet AI Universal Intelligence Engine. It details the multi-agent architecture, the vectorized machine learning pipeline, and the "God-mode" coaching brain developed for ASEAN youth financial empowerment.

---

## 1. The Financial Problem & My AI Solution

ByteWallet AI shifts the paradigm from retrospective charts to prospective, predictive intelligence. The engine doesn't just show what you spent; it uses a **Hybrid Multi-Agent System** to intercept your current trajectory. 

**Condition-1 (Liquidity Shortfall)**: This is a core innovation. The system predicts if your projected cash in hand—after non-essential "extra" spending—will cover upcoming rent and utilities. If a deficit is detected, the AI calculates a specific **Cutback Target** (e.g., "Cut 4 Shopping purchases to save 400k VND").

---

## 2. The Machine Learning Pipeline

### Production-Grade Vectorization
The engine processes **662,268 transaction rows** using 100% vectorized Pandas operations. This allows the feature extraction for 19 behavioral features (Pacing, Impulse, Velocity Delta) to execute in under **6 seconds** locally.

### Balanced Shortfall Prediction
Using a `GradientBoostingClassifier` within a Scikit-Learn Pipeline, the model achieves **98.0% Accuracy** and a **99.63% ROC-AUC**. The high precision (98%) ensures that when the AI warns a user, it is correct, preventing "coaching fatigue" from false alarms.

---

## 3. Universal Multi-Agent Intelligence (Phase 4.5)

The latest architecture orchestrates 6 independent specialists that run concurrently during every API call:

1.  **Liquidity Agent**: Monitors (Balance - 30d projected extra spend) vs Essential Bills.
2.  **Income Agent**: Detects late paychecks or significant income drops from gig-work.
3.  **Goal Agent**: Tracks pacing towards specific user savings targets (e.g., "New Bike").
4.  **Anomaly Agent**: Flags outliers (>$2.5\sigma$) and duplicate charges locally.
5.  **Subscription Agent**: Detects silent price hikes in recurring services.
6.  **Savings Agent**: Nudges users to move idle cash into yield-bearing accounts.

---

## 4. The "God-mode" Messaging Aggregator

To avoid overwhelming the user with 6 different alerts, I built a centralized **Signal Aggregator** in the Messaging Service:

-   **Priority Ranking**: Signals are ranked by **Life Impact** (Liquidity > Security > Waste > Goals).
-   **Synthesis**: The top 2 signals are fed into a local **Ollama LLM (qwen2.5)** with a 10s fast-fallback. The LLM synthesizes these into a single, supportive 2-sentence coaching tip.
-   **Numerical Precision**: The aggregator extracts metadata (Shortfall Amount, Items to Cut) from the agents to ensure the coaching is statistically grounded, not just generic text.

---

## 5. Federated Learning & Privacy

ByteWallet AI remains **100% Offline and Privacy-First**. No raw financial data leaves the hardware.
- **Local Summarization**: All synthesis occurs on-device.
- **FedAvg Foundation**: The system is built on a Federated Learning foundation, allowing the global model to learn from weight deltas without ever seeing a single private transaction.

---

**ByteWallet AI Innovation v2.1**
*Empowering financial foresight through universal, privacy-first intelligence.*
