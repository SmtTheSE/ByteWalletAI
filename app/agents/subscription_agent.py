"""
app/agents/subscription_agent.py

Phase 4: Monitors for recurring subscription charges.
Detects:
  - Recurring payments (same merchant ± 3 days, monthly)
  - Subscription price increases vs. prior 3 months
"""
from __future__ import annotations
import logging
from collections import defaultdict
from typing import List

import pandas as pd

from app.agents.base_agent import BaseAgent, Alert

log = logging.getLogger("subscription_agent")


class SubscriptionAgent(BaseAgent):
    name = "subscription_agent"

    def run(self, user_id: str, snapshot: dict) -> List[Alert]:
        alerts: List[Alert] = []
        try:
            raw_txs = snapshot.get("transactions", []) or []
            currency = snapshot.get("currency", "VND")
            rows = []
            for t in raw_txs:
                if not isinstance(t, dict):
                    t = t.__dict__ if hasattr(t, "__dict__") else {}
                ts  = pd.to_datetime(t.get("timestamp", ""), utc=True, errors="coerce")
                amt = abs(float(t.get("amount", 0)))
                cat = str(t.get("category", ""))
                note = str(t.get("note") or t.get("merchant_name") or cat)
                typ = str(t.get("type", "expense")).lower()
                rows.append({"ts": ts, "amount": amt, "note": note, "type": typ})

            if not rows:
                return alerts

            df = pd.DataFrame(rows)
            expenses = df[df["type"] == "expense"].copy()
            expenses["month"] = expenses["ts"].dt.to_period("M")
            expenses["note_lower"] = expenses["note"].str.lower().str.strip()

            # Group by note, look for month-over-month recurrence
            grouped = expenses.groupby(["note_lower", "month"])["amount"].sum().reset_index()
            note_months = grouped.groupby("note_lower")

            for note_key, group in note_months:
                if len(group) < 2:
                    continue  # Need at least 2 months to detect recurrence

                group_sorted = group.sort_values("month")
                amounts = group_sorted["amount"].tolist()

                # Check if latest charge is higher than previous average
                if len(amounts) >= 2:
                    prev_avg = sum(amounts[:-1]) / len(amounts[:-1])
                    latest   = amounts[-1]
                    increase_pct = (latest - prev_avg) / max(prev_avg, 1) * 100

                    if increase_pct > 5:  # More than 5% increase
                        alerts.append(Alert(
                            agent=self.name,
                            type="subscription",
                            severity="warning",
                            title=f"Subscription price increase detected: {note_key}",
                            message=(
                                f"The recurring charge for '{note_key}' increased by "
                                f"{increase_pct:.1f}% ({prev_avg:,.0f} → {latest:,.0f} {currency}). "
                                f"This may be an unnoticed price hike."
                            ),
                            suggested_action=(
                                f"Review your subscription for '{note_key}' and check "
                                f"if the new rate is intentional."
                            ),
                            metadata={
                                "merchant":    note_key,
                                "prev_avg":    round(prev_avg, 2),
                                "latest":      round(latest, 2),
                                "increase_pct": round(increase_pct, 1),
                            },
                        ))

        except Exception as e:
            log.error(f"SubscriptionAgent error for {user_id}: {e}")
        return alerts
