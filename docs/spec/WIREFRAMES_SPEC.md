# ByteWallet AI - Wireframes & Visual Specifications
## For AI Ready ASEAN Youth Challenge Submission

---

## WIREFRAME 1: Home Dashboard (Mobile App)

### Layout Overview
```
┌─────────────────────────────────────┐
│  [Hamburger Menu]    ByteWallet AI  │
│                                     │
│  ┌───────────────────────────────┐ │
│  │                               │ │
│  │     SAFE TO SPEND TODAY       │ │
│  │           ฿ 245,000           │ │
│  │                               │ │
│  │   Month-End Balance Forecast  │ │
│  │   ┌─────────────────────┐     │ │
│  │   │  ✓ On Track         │     │ │
│  │   │  +฿180,000          │     │ │
│  │   └─────────────────────┘     │ │
│  └───────────────────────────────┘ │
│                                     │
│  Quick Stats:                       │
│  ┌──────────┬──────────┬──────────┐│
│  │ Budget   │ Days     │ Risk     ││
│  │ Used 42% │ 12/30    │ Low 15%  ││
│  └──────────┴──────────┴──────────┘│
│                                     │
│  Recent Alerts:                     │
│  ⚠️ Food spending up 23% this week │
│                                     │
│  [Bottom Nav: Home | Analytics |    │
│            Insights | Settings]     │
└─────────────────────────────────────┘
```

### Key Features Explained

**Safe to Spend Today:**
- Calculation: `(Remaining Budget - Predicted Essential Expenses) / Days Left`
- Updated in real-time after every transaction
- Color-coded: Green (>20% buffer), Yellow (10-20%), Red (<10%)

**Month-End Forecast Card:**
- Shows predicted balance using ML model
- Includes confidence interval (±10%)
- Updates with each transaction via federated inference

**Quick Stats Row:**
- Budget Used: Percentage of monthly budget consumed
- Days: Current day vs. total days in month
- Risk: Traffic light indicator based on shortfall probability

---

## WIREFRAME 2: Prediction Detail Screen

### Layout
```
┌─────────────────────────────────────┐
│  ← Back        Prediction Details   │
│                                     │
│  YOUR BURN RATE ANALYSIS            │
│  Updated: Just now                  │
│                                     │
│  ┌───────────────────────────────┐ │
│  │                               │ │
│  │     Shortfall Probability     │ │
│  │                               │ │
│  │         83% HIGH RISK         │ │
│  │                               │ │
│  │    [Gauge Visualization]      │ │
│  │    0% ────●─────── 100%       │ │
│  │         Safe    Danger        │ │
│  └───────────────────────────────┘ │
│                                     │
│  Why This Prediction?               │
│  ┌───────────────────────────────┐ │
│  │ ⚠️ Delta Spend Rate: +35%     │ │
│  │ Your spending velocity is     │ │
│  │ 35% higher than your normal   │ │
│  │                               │ │
│  │ ⚠️ Food Category Spike        │ │
│  │ Food: 229k → 396k (projected) │ │
│  │                               │ │
│  │ ℹ️ Day 15 of 30 (50% month)   │ │
│  │ You've used 68% of budget     │ │
│  └───────────────────────────────┘ │
│                                     │
│  Recommended Actions:               │
│  ┌───────────────────────────────┐ │
│  │ 🍳 Cook at home for 3 days    │ │
│  │    Save: ~90,000 VND          │ │
│  │                               │ │
│  │ 🚫 Skip Starbucks this week   │ │
│  │    Save: ~45,000 VND          │ │
│  │                               │ │
│  │ 💸 Avoid online shopping      │ │
│  │    Save: ~120,000 VND         │ │
│  └───────────────────────────────┘ │
│                                     │
│  [Button: Set Spending Alert]       │
│  [Button: Chat with AI Coach]       │
└─────────────────────────────────────┘
```

### Feature Importance Visualization

**Top Risk Factors (Dynamic):**
1. `delta_spend_rate`: Shows deviation from historical norm
2. `budget_used_percent`: Compares spend pace vs. time progress
3. `category_spike`: Highlights specific overspending categories
4. `prev_month_overspend`: Reminds if user failed last month

---

## WIREFRAME 3: AI Coach Chat Interface

### Layout
```
┌─────────────────────────────────────┐
│  ← Back        AI Financial Coach   │
│                                     │
│  ┌───────────────────────────────┐ │
│  │ 🤖 ByteBot                    │ │
│  │ Hey Sitt! I noticed your      │ │
│  │ Food spending jumped 35%      │ │
│  │ this week. Want to talk about │ │
│  │ it?                           │ │
│  │             10:42 AM          │ │
│  └───────────────────────────────┘ │
│                                     │
│  ┌───────────────────────────────┐ │
│  │ Yeah, I've been eating out    │ │
│  │ a lot during exams 😅         │ │
│  │                   You • 10:43 │ │
│  └───────────────────────────────┘ │
│                                     │
│  ┌───────────────────────────────┐ │
│  │ 🤖 Totally get it! Exams are  │ │
│  │ stressful. Here's the thing:  │ │
│  │                               │ │
│  │ If you cook just 2 meals at   │ │
│  │ home instead of 1, you'll     │ │
│  │ save ~60,000 VND/day.         │ │
│  │                               │ │
│  │ That's 180k this week—enough  │ │
│  │ to cover your transport costs │ │
│  │ for the whole month! 🎯       │ │
│  │             10:43 AM          │ │
│  └───────────────────────────────┘ │
│                                     │
│  ┌───────────────────────────────┐ │
│  │ 💡 Quick Win Ideas:           │ │
│  │ • Meal prep on Sunday         │ │
│  │ • Use GrabFood promo codes    │ │
│  │ • Split orders with friends   │ │
│  └───────────────────────────────┘ │
│                                     │
│  [Type a message...]         [Send] │
└─────────────────────────────────────┘
```

### AI Personality Traits
- **Empathetic**: Understands stress, doesn't judge
- **Specific**: Gives exact numbers, not vague advice
- **Actionable**: Provides concrete steps, not just warnings
- **Encouraging**: Celebrates small wins, builds habits

---

## WIREFRAME 4: Category Breakdown with AI Insights

### Layout
```
┌─────────────────────────────────────┐
│  ← Back        Spending Insights    │
│                                     │
│  March 2026                         │
│  Total Spent: ฿ 8,450               │
│                                     │
│  By Category:                       │
│  ┌───────────────────────────────┐ │
│  │ 🍔 Food & Drink    45%        │ │
│  │ ████████░░░░░ 3,800   🔴 +23% │ │
│  │                               │ │
│  │ 🚗 Transport       18%        │ │
│  │ ████░░░░░░░░░ 1,520   🟢 -5%  │ │
│  │                               │ │
│  │ 🛍️ Shopping       15%         │ │
│  │ ███░░░░░░░░░░ 1,260   🟡 +8%  │ │
│  │                               │ │
│  │ 🏠 Rent            12%        │ │
│  │ ██░░░░░░░░░░░ 1,015   ✅ 0%   │ │
│  │                               │ │
│  │ 🎬 Entertainment  10%         │ │
│  │ ██░░░░░░░░░░░   845    🟡 +12%│ │
│  └───────────────────────────────┘ │
│                                     │
│  AI Insight:                        │
│  ┌───────────────────────────────┐ │
│  │ ⚠️ Your Food spending is on   │ │
│  │ track to exceed last month by │ │
│  │ 23%. Main drivers:            │ │
│  │ • Bubble tea: 5 visits/week   │ │
│  │ • Late-night delivery: +฿400  │ │
│  │                               │ │
│  │ 💡 Try this: Limit bubble tea │ │
│  │ to 2x/week = save ฿300/month │ │
│  └───────────────────────────────┘ │
│                                     │
│  [Button: Set Category Budget]      │
└─────────────────────────────────────┘
```

---

## WIREFRAME 5: Federated Learning Status

### Layout
```
┌─────────────────────────────────────┐
│  Settings      Privacy & AI         │
│                                     │
│  Federated Learning                 │
│  ┌───────────────────────────────┐ │
│  │                               │ │
│  │  ✅ Active                    │ │
│  │                               │ │
│  │  Your device is helping      │ │
│  │  improve ByteWallet AI for   │ │
│  │  all users—without sharing   │ │
│  │  your private data.          │ │
│  │                               │ │
│  │  Last Model Update:          │ │
│  │  Today, 3:42 AM              │ │
│  │                               │ │
│  │  Data Sent: 0 transactions   │ │
│  │  (Only mathematical weights) │ │
│  │                               │ │
│  │  Your Contribution:          │ │
│  │  ████████████░░ 87% complete │ │
│  └───────────────────────────────┘ │
│                                     │
│  Privacy Guarantees:                │
│  ✅ Transactions never leave device │
│  ✅ No PII transmitted              │
│  ✅ Differential privacy enabled    │
│  ✅ You can opt-out anytime         │
│                                     │
│  [Toggle: Enable Federated Learning]│
│  [Button: View Technical Details]   │
└─────────────────────────────────────┘
```

---

## CHARTS & DIAGRAMS FOR PROPOSAL

### Diagram 1: System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    BYTEWALLET AI                        │
│              Hybrid AI Architecture                     │
└─────────────────────────────────────────────────────────┘

┌─────────────┐
│   User      │
│  Transaction│
│   (API Call)│
└──────┬──────┘
       │
       ▼
┌──────────────────────────────────────────────────────┐
│              FastAPI Backend (Cloud/Edge)            │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │  1. Feature Engineering Service              │   │
│  │     • Temporal features (day, progress)      │   │
│  │     • Velocity metrics (burn rate, delta)    │   │
│  │     • Category distributions (19 features)   │   │
│  └──────────────────────────────────────────────┘   │
│                     │                                │
│                     ▼                                │
│  ┌──────────────────────────────────────────────┐   │
│  │  2. ML Inference Engine                      │   │
│  │     GradientBoostingClassifier                │   │
│  │     Accuracy: 99.6% ROC-AUC                   │   │
│  │     Output: Shortfall Probability (0-1)       │   │
│  └──────────────────────────────────────────────┘   │
│                     │                                │
│                     ▼                                │
│  ┌──────────────────────────────────────────────┐   │
│  │  3. Multi-Agent Orchestrator                 │   │
│  │     • Subscription Agent                     │   │
│  │     • Anomaly Agent                          │   │
│  │     • Savings Agent                          │   │
│  └──────────────────────────────────────────────┘   │
│                     │                                │
│                     ▼                                │
│  ┌──────────────────────────────────────────────┐   │
│  │  4. Messaging Service                        │   │
│  │     • Ollama LLM (Qwen2.5)                   │   │
│  │     • Adaptive Regex Fallback                │   │
│  │     • Personalized Coaching Message          │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
└──────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────┐
│              Response to User                        │
│  { risk_level, shortfall_prob, ai_message, ... }     │
└──────────────────────────────────────────────────────┘

       Parallel Process: Federated Learning
┌──────────────────────────────────────────────────────┐
│  User Device trains local model overnight            │
│       ↓                                               │
│  Sends only weight deltas (not raw data)             │
│       ↓                                               │
│  Central server aggregates updates (FedAvg)          │
│       ↓                                               │
│  Improved global model pushed back to devices        │
└──────────────────────────────────────────────────────┘
```

### Diagram 2: Feature Importance Chart

```
Feature Importance Scores (Top 10):

delta_spend_rate          ████████████████████  0.24
budget_used_percent       ██████████████████    0.21
progress                  ████████████████      0.18
avg_daily_spend_mtd       ██████████████        0.15
prev_month_overspend      ████████████          0.12
pct_food                  ██████████            0.10
cash_flow_ratio           ████████              0.08
days_in_month             ██████                0.06
spend_mtd                 ████                  0.04
income_mtd                ██                    0.02

(Generated from trained GradientBoostingClassifier)
```

### Diagram 3: User Journey Flow

```
┌──────────────┐
│  User makes  │
│  transaction │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  API call to │
│  /predict-   │
│  burn-rate   │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Real-time   │
│  feature     │
│  engineering │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  ML model    │
│  predicts    │
│  shortfall   │
│  probability │
└──────┬───────┘
       │
       ▼
┌──────────────┐     ┌──────────────┐
│  LOW RISK    │     │  HIGH RISK   │
│  (<50%)      │     │  (>85%)      │
└──────┬───────┘     └──────┬───────┘
       │                    │
       ▼                    ▼
┌──────────────┐     ┌──────────────┐
│  Gentle      │     │  Multi-Agent │
│  reminder    │     │  Analysis    │
│  notification│     │  + LLM       │
│              │     │  Coaching    │
└──────┬───────┘     └──────┬───────┘
       │                    │
       └────────┬───────────┘
                │
                ▼
       ┌────────────────┐
       │  User receives │
       │  actionable    │
       │  insight       │
       └────────────────┘
```

---

## COLOR PALETTE & BRANDING

### Primary Colors
- **Deep Blue**: `#1E3A8A` (Trust, Intelligence, Technology)
- **Emerald Green**: `#10B981` (Financial Success, Growth)
- **Coral Red**: `#EF4444` (Urgency, Warnings)

### Secondary Colors
- **Sky Blue**: `#3B82F6` (Accents, Links)
- **Amber**: `#F59E0B` (Caution alerts)
- **Slate Gray**: `#64748B` (Secondary text)

### Usage Guidelines
- **Success states**: Emerald Green
- **Warning states**: Amber
- **Danger states**: Coral Red
- **Primary CTAs**: Deep Blue
- **Links & Interactive**: Sky Blue

### Typography
- **Headings**: Arial Bold (as per competition requirements)
- **Body**: Arial Regular
- **Code/Mono**: Courier New or Fira Code
- **Sizes**: 12pt body, 14-18pt headings

---

## EXPORT SPECIFICATIONS

### For PDF Proposal
- **Format**: A4 or Letter size
- **Resolution**: 300 DPI minimum for print
- **Color Mode**: RGB (digital submission)
- **File Size**: <10 MB (check portal limits)

### For Video Pitch
- **Resolution**: 1920x1080 (Full HD) or 1280x720 (HD)
- **Aspect Ratio**: 16:9
- **Frame Rate**: 30 fps
- **Format**: MP4 (H.264 codec)
- **Audio**: AAC, 44.1 kHz, stereo

### For Screenshots/Mockups
- **Tool Recommendations**:
  - Figma (free for individuals)
  - Canva (free tier available)
  - Adobe XD (free starter plan)
- **Export**: PNG @2x for retina displays
- **Background**: Transparent or solid color (no busy backgrounds)

---

## IMPLEMENTATION ROADMAP VISUALIZATION

### Gantt Chart (Text Version)

```
Phase 1: MVP (✅ Completed Q1 2026)
[██████████] 100%

Phase 2: Pilot (Q2 2026)
          [████████░░] 80% (Apr-Jun)

Phase 3: Scale (Q3-Q4 2026)
                    [████████████] 50% (Jul-Dec)

Phase 4: Regional (2027)
                              [████████░░░░░░] 30%
```

---

## SUBMISSION CHECKLIST FOR VISUAL ASSETS

- [ ] All 5 wireframes created in high resolution
- [ ] System architecture diagram included in proposal
- [ ] Feature importance chart visualized
- [ ] User journey flowchart added
- [ ] Color palette documented
- [ ] At least 2 screenshots of working prototype
- [ ] Logo designed (even if simple text-based)
- [ ] All images have alt text for accessibility
- [ ] File names descriptive (e.g., "wireframe_home_screen.png")
- [ ] Total attachment size <25 MB

---

**Note:** These wireframes can be quickly prototyped in Figma using free UI kits. Search for "Mobile Banking UI Kit" or "Finance Dashboard Template" to accelerate design.
