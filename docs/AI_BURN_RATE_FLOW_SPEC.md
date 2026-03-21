# 🧠 ByteWallet AI: Predictive "Burn Rate" Alerts
## Final Engineering Specification (v2.2)

The **Predictive Burn Rate Alert** is a proactive AI feature designed to shift financial tracking from *retrospective* (what you spent) to *prospective* (what you will have).

---

## 🏗️ System Architecture (100% Local Hybrid)

```mermaid
graph TD
    A[Cron Job / User Trigger] --> B[Supabase Edge Function]
    B --> C[Fetch User Snapshot]
    C --> D[POST to ByteWallet AI Service]
    D --> E[Adaptive Risk Engine]
    E --> F[Universal Intelligence Agents 7x]
    F --> |Aggregate Signals| G{God-mode Messaging Brain}
    G --> |High Priority| H[Ollama Local LLM]
    G --> |Fallback| I[Multi-Agent Rules Body]
    H & I --> J[Return JSON with Proactive Alerts]
    J --> K[Insert Notifications in Supabase]
    K --> L[Push to App Toast/Badge/Modal]
```

---

## 🛠️ Step-by-Step Flow

### 1. Data Collection Phase
The system fetches a "Snapshot" of the user's financial health:
- **Transactions**: Baseline + Current month.
- **Wallet Status**: Real-time Banking and Cash balances.
- **Monthly Budget**: User-defined limits (Dynamic, no hardcoded defaults).
- **Fixed Obligations**: Automated recurrence detection + Explicit user bills.
- **Savings Goals**: Target amounts and deadlines.

### 2. Multi-Agent Intelligence (Phase 4.5)
The **ByteWallet AI Microservice** now orchestrates 7 autonomous agents:
1.  **Liquidity Agent (Condition-1)**: Compares (Balance - 30d Extra) vs Essential Bills. Identifies shortfalls and provides cutback targets.
2.  **Mid-Month Agent (Condition-2)**: Monitors discretionary spend usage specifically on the 14th-16th. Alerts if >50% of discretionary baseline is spent.
3.  **Income Agent**: Detects late salaries or significant gig-earnings drops.
4.  **Goal Agent**: Tracks pacing toward user-defined savings targets.
5.  **Anomaly Agent**: Flags unusual spikes or duplicate transactions.
6.  **Subscription Agent**: Monitors price hikes in recurring services.
7.  **Savings Agent**: Nudges users to move idle cash into yield-bearing accounts.

### 3. God-mode Coaching Brain
Logic executed in the **Messaging Service**:
- **Signal Aggregator**: Ranks all agent findings by **Life Impact Priority** (Liquidity > Security > Waste > Goals).
- **Consolidated Prompting**: Feeds the top 2 prioritized signals into the local Ollama LLM (`qwen2.5`) for a single, synthesized coaching tip.

---

**ByteWallet AI Innovation v2.2**
*Empowering financial foresight through universal, multi-agent intelligence.*
