"""
app/agents/savings_agent.py

Phase 4: Monitors savings velocity and goal progress.
Detects:
  - User is ahead of savings pace → nudge to save more
  - Income month-to-date but no savings movement → recommend transfer
  - Savings goal within reach with small behaviour change
"""
from __future__ import annotations
import logging
import calendar
from datetime import datetime, timezone
from typing import List

import pandas as pd

from app.agents.base_agent import BaseAgent, Alert

log = logging.getLogger("savings_agent")


class SavingsAgent(BaseAgent):
    name = "savings_agent"

    def run(self, user_id: str, snapshot: dict) -> List[Alert]:
        alerts: List[Alert] = []
        try:
            currency     = snapshot.get("currency", "VND")
            current_date = pd.to_datetime(snapshot.get("current_date", datetime.now(timezone.utc).date()))
            day          = current_date.day
            days_in_month = calendar.monthrange(current_date.year, current_date.month)[1]
            progress     = day / days_in_month

            # Balances
            balances = snapshot.get("balances", {})
            if hasattr(balances, "__dict__"):
                balances = balances.__dict__
            total_balance = float(balances.get("banking", 0)) + float(balances.get("cash", 0))

            # Budget
            budget = snapshot.get("monthly_budget", {})
            if hasattr(budget, "__dict__"):
                budget = budget.__dict__
            budget_total = float(budget.get("total", 0))

            # Essential obligations
            obligations = snapshot.get("essential_obligations", []) or []
            essential_total = sum(
                float(o.get("amount", 0) if isinstance(o, dict) else getattr(o, "amount", 0))
                for o in obligations
            )

            # Transactions this month
            raw_txs = snapshot.get("transactions", []) or []
            month_start = pd.Timestamp(year=current_date.year, month=current_date.month, day=1, tz="UTC")
            current_ts  = pd.Timestamp(current_date.date(), tz="UTC")

            income_mtd, spend_mtd = 0.0, 0.0
            for t in raw_txs:
                if not isinstance(t, dict):
                    t = t.__dict__ if hasattr(t, "__dict__") else {}
                ts  = pd.to_datetime(t.get("timestamp", ""), utc=True, errors="coerce")
                amt = abs(float(t.get("amount", 0)))
                typ = str(t.get("type", "expense")).lower()
                if pd.notna(ts) and month_start <= ts <= current_ts:
                    if typ == "income":
                        income_mtd += amt
                    elif typ == "expense":
                        spend_mtd += amt

            #  Savings pace check 
            disposable       = income_mtd - spend_mtd - essential_total
            recommended_save = budget_total * 0.20  # 20% savings rate target

            if disposable > 0 and progress >= 0.5:
                # Midmonth and still in the green
                alerts.append(Alert(
                    agent=self.name,
                    type="savings",
                    severity="info",
                    title="Great pacing! Consider boosting savings now.",
                    message=(
                        f"At the midpoint of the month, approximately "
                        f"{disposable:,.0f} {currency} in disposable income is available. "
                        f"Moving a portion to savings now locks in progress before end-of-month expenses arrive."
                    ),
                    suggested_action=(
                        f"Consider transferring {min(disposable * 0.5, recommended_save):,.0f} {currency} "
                        f"to a savings account today."
                    ),
                    metadata={
                        "disposable_income": round(disposable, 2),
                        "suggested_transfer": round(min(disposable * 0.5, recommended_save), 2),
                    },
                ))

            #  No savings movement despite income 
            if income_mtd > 0 and spend_mtd < income_mtd * 0.7 and total_balance > budget_total * 0.3:
                alerts.append(Alert(
                    agent=self.name,
                    type="savings",
                    severity="info",
                    title="Spending well under budget — idle cash detected.",
                    message=(
                        f"Spending this month is only {spend_mtd / max(income_mtd, 1) * 100:.0f}% of income. "
                        f"The current balance of {total_balance:,.0f} {currency} could be working harder."
                    ),
                    suggested_action=(
                        "Explore moving idle cash into a savings account, "
                        "or allocate toward an emergency fund."
                    ),
                    metadata={
                        "income_mtd": round(income_mtd, 2),
                        "spend_mtd":  round(spend_mtd, 2),
                        "balance":    round(total_balance, 2),
                    },
                ))

        except Exception as e:
            log.error(f"SavingsAgent error for {user_id}: {e}")
        return alerts
