"""
app/agents/income_agent.py

Monitors for irregular income patterns, drops, or late paychecks.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import List

import pandas as pd
from app.agents.base_agent import BaseAgent, Alert

log = logging.getLogger("income_agent")

class IncomeAgent(BaseAgent):
    name = "income_agent"

    def run(self, user_id: str, snapshot: dict) -> List[Alert]:
        alerts: List[Alert] = []
        try:
            currency = snapshot.get("currency", "VND")
            current_date = pd.to_datetime(snapshot.get("current_date", datetime.now(timezone.utc).date()))
            
            # 1. Parse all transactions
            raw_txs = snapshot.get("transactions", []) or []
            rows = []
            for t in raw_txs:
                if not isinstance(t, dict):
                    t = t.__dict__ if hasattr(t, "__dict__") else {}
                ts = pd.to_datetime(t.get("timestamp", ""), utc=True, errors="coerce")
                amt = abs(float(t.get("amount", 0)))
                typ = str(t.get("type", "expense")).lower()
                cat = str(t.get("category", "Other")).lower()
                rows.append({"ts": ts, "amount": amt, "type": typ, "category": cat})

            if not rows:
                return alerts

            df = pd.DataFrame(rows)
            income_df = df[df["type"] == "income"].copy()
            if income_df.empty:
                # If history is missing, we can't detect "late" income yet
                return alerts

            income_df["month"] = income_df["ts"].dt.to_period("M")
            income_df["day"] = income_df["ts"].dt.day
            
            # 2. Historical Analysis (Last 3 months)
            current_month = current_date.to_period("M")
            hist_income = income_df[income_df["month"] < current_month].copy()
            
            if hist_income.empty:
                return alerts

            monthly_avg = hist_income.groupby("month")["amount"].sum().mean()
            avg_arrival_day = hist_income.groupby("month")["day"].min().mean() # Simplification: first income of month

            # 3. Current Month Check
            curr_income = income_df[income_df["month"] == current_month].copy()
            curr_total = curr_income["amount"].sum()

            # Situation A: Late Income
            if curr_income.empty and current_date.day > (avg_arrival_day + 5):
                alerts.append(Alert(
                    agent=self.name,
                    type="info",
                    severity="warning",
                    title="Expected income is late.",
                    message=(
                        f"Your regular income usually arrives around the {int(avg_arrival_day)}th. "
                        f"It is now the {current_date.day}th and hasn't been recorded yet."
                    ),
                    suggested_action="Check with your provider or update your records to ensure your burn-rate prediction stays accurate.",
                    metadata={"avg_day": int(avg_arrival_day), "current_day": current_date.day}
                ))

            # Situation B: Significant Income Drop
            elif not curr_income.empty and curr_total < (monthly_avg * 0.70) and current_date.day > 25:
                # Only warn of a drop near end of month
                alerts.append(Alert(
                    agent=self.name,
                    type="info",
                    severity="warning",
                    title="Significant income drop detected.",
                    message=(
                        f"Your income this month ({curr_total:,.0f} {currency}) is about "
                        f"{((monthly_avg - curr_total) / monthly_avg) * 100:.0f}% lower than your typical average."
                    ),
                    suggested_action="Consider tightening your budget for the next few weeks to compensate for the lower earnings.",
                    metadata={"monthly_avg": round(monthly_avg, 2), "curr_total": round(curr_total, 2)}
                ))

        except Exception as e:
            log.error(f"IncomeAgent error for {user_id}: {e}")
        return alerts
