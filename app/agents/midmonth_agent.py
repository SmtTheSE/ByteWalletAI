"""
app/agents/midmonth_agent.py

Condition-2: Mid-Month Discretionary Check.
Logic: 
  Actual Balance (Baseline) = Total Balance - Essential Obligations.
  If it's Mid-Month (14-16th) AND Current Discretionary Usage > 50% of Actual Balance, show alert.
"""
from __future__ import annotations
import logging
from typing import List
import pandas as pd
from app.agents.base_agent import BaseAgent, Alert

log = logging.getLogger("midmonth_agent")

ESSENTIAL_CATEGORIES = {"rent", "subscription", "education", "utilities", "bills"}

class MidMonthAgent(BaseAgent):
    name = "midmonth_agent"

    def run(self, user_id: str, snapshot: dict) -> List[Alert]:
        alerts: List[Alert] = []
        try:
            current_date_str = snapshot.get("current_date", "")
            if not current_date_str:
                return alerts
            
            curr_date = pd.to_datetime(current_date_str)
            day = curr_date.day
            
            # Mid-month trigger: 14th to 16th
            if not (14 <= day <= 16):
                return alerts

            currency = snapshot.get("currency", "VND")
            
            # 1. Calculate Actual Balance (Discretionary Baseline)
            balances = snapshot.get("balances", {})
            if hasattr(balances, "__dict__"):
                balances = balances.__dict__
            total_balance = float(balances.get("banking", 0)) + float(balances.get("cash", 0))

            obligations = snapshot.get("essential_obligations", []) or []
            essential_total = sum(
                float(o.get("amount", 0) if isinstance(o, dict) else getattr(o, "amount", 0))
                for o in obligations
            )
            
            actual_balance_baseline = total_balance - essential_total
            if actual_balance_baseline <= 0:
                return alerts # Already in a liquidity crisis, LiquidityAgent will handle it

            # 2. Calculate Current Discretionary Usage (Spent this month so far)
            raw_txs = snapshot.get("transactions", []) or []
            discretionary_spent = 0
            for t in raw_txs:
                if not isinstance(t, dict):
                    t = t.__dict__ if hasattr(t, "__dict__") else {}
                
                # Check if it's an expense in the current month
                ts = pd.to_datetime(t.get("timestamp", ""), utc=True, errors="coerce")
                if ts.month == curr_date.month and ts.year == curr_date.year:
                    amt = abs(float(t.get("amount", 0)))
                    cat = str(t.get("category", "Other")).lower().strip()
                    typ = str(t.get("type", "expense")).lower()
                    
                    if typ == "expense" and cat not in ESSENTIAL_CATEGORIES:
                        discretionary_spent += amt

            # 3. Check Condition: Usage > 50% of Actual Balance
            usage_ratio = discretionary_spent / actual_balance_baseline
            
            if usage_ratio > 0.5:
                alerts.append(Alert(
                    agent=self.name,
                    type="midmonth_check",
                    severity="warning",
                    title="Mid-Month Discretionary Warning",
                    message=(
                        f"Wait! You've already used {usage_ratio*100:.1f}% of your "
                        f"available discretionary funds ({actual_balance_baseline:,.0f} {currency}) "
                        f"only halfway through the month."
                    ),
                    suggested_action=(
                        "Try to slow down on non-essential spending for the next 7 days "
                        "to ensure you stay balanced until the end of the month."
                    ),
                    metadata={
                        "actual_balance_baseline": round(actual_balance_baseline, 2),
                        "discretionary_spent": round(discretionary_spent, 2),
                        "usage_ratio": round(usage_ratio, 3)
                    }
                ))

        except Exception as e:
            log.error(f"MidMonthAgent error for {user_id}: {e}")
        return alerts
