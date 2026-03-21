"""
app/agents/liquidity_agent.py

Condition-1: Monitors for essential expense liquidity shortfalls.
Logic:
  Compare (Total Balance - Projected 30-day extra expenses) vs Essential Obligations.
  If shortfall detected, recommend specific cutbacks in less-important categories.
"""
from __future__ import annotations
import logging
import math
from typing import List

import pandas as pd
from app.agents.base_agent import BaseAgent, Alert

log = logging.getLogger("liquidity_agent")

ESSENTIAL_CATEGORIES = {"rent", "subscription", "education", "utilities", "bills"}
LESS_IMPORTANT_CATEGORIES = {"shopping", "entertainment", "food", "lifestyle"}

class LiquidityAgent(BaseAgent):
    name = "liquidity_agent"

    def run(self, user_id: str, snapshot: dict) -> List[Alert]:
        alerts: List[Alert] = []
        try:
            currency = snapshot.get("currency", "VND")
            
            # 1. Get current liquidity (Cash + Bank)
            balances = snapshot.get("balances", {})
            if hasattr(balances, "__dict__"):
                balances = balances.__dict__
            total_balance = float(balances.get("banking", 0)) + float(balances.get("cash", 0))

            # 2. Get upcoming essential obligations
            obligations = snapshot.get("essential_obligations", []) or []
            essential_total = sum(
                float(o.get("amount", 0) if isinstance(o, dict) else getattr(o, "amount", 0))
                for o in obligations
            )
            
            if not obligations:
                return alerts # No obligations, no liquidity risk detected here

            # 3. Analyze transactions to find "Extra Expenses" (Non-essential)
            raw_txs = snapshot.get("transactions", []) or []
            rows = []
            for t in raw_txs:
                if not isinstance(t, dict):
                    t = t.__dict__ if hasattr(t, "__dict__") else {}
                ts = pd.to_datetime(t.get("timestamp", ""), utc=True, errors="coerce")
                amt = abs(float(t.get("amount", 0)))
                cat = str(t.get("category", "Other")).lower().strip()
                typ = str(t.get("type", "expense")).lower()
                rows.append({"ts": ts, "amount": amt, "category": cat, "type": typ})

            if not rows:
                return alerts

            df = pd.DataFrame(rows)
            expenses = df[df["type"] == "expense"].copy()
            if expenses.empty:
                return alerts

            # Identify "Less Important" spend
            less_important = expenses[expenses["category"].isin(LESS_IMPORTANT_CATEGORIES)].copy()
            
            # Determine daily "Extra" spend rate (use last 30 days if possible)
            max_date = expenses["ts"].max()
            min_date = expenses["ts"].min()
            timespan_days = max((max_date - min_date).days, 1)
            
            total_extra_spend = less_important["amount"].sum()
            daily_extra_rate = total_extra_spend / timespan_days
            projected_30d_extra = daily_extra_rate * 30

            # 4. Core Logic: (Balance - 30d Extra) < Essential Obligations
            projected_balance_in_hand = total_balance - projected_30d_extra
            
            if projected_balance_in_hand < essential_total:
                shortfall = essential_total - projected_balance_in_hand
                
                # Identify the top "Less Important" category to cut from
                cat_summary = less_important.groupby("category").agg(
                    total_amt=("amount", "sum"),
                    avg_price=("amount", "mean"),
                    count=("amount", "count")
                ).sort_values("total_amt", ascending=False)
                
                if not cat_summary.empty:
                    top_cat = cat_summary.index[0]
                    avg_item_price = cat_summary.loc[top_cat, "avg_price"]
                    
                    # Prevent division by zero
                    if avg_item_price > 0:
                        items_to_cut = math.ceil(shortfall / avg_item_price)
                        
                        alerts.append(Alert(
                            agent=self.name,
                            type="liquidity",
                            severity="critical",
                            title="Upcoming Bill Shortfall Detected",
                            message=(
                                f"Your projected balance in hand ({projected_balance_in_hand:,.0f} {currency}) "
                                f"will not cover upcoming essential bills worth {essential_total:,.0f} {currency}. "
                                f"You need approximately {shortfall:,.0f} {currency} more."
                            ),
                            suggested_action=(
                                f"Cutting ~{items_to_cut} {top_cat} purchases "
                                f"(avg {avg_item_price:,.0f} {currency} each) would cover this shortfall."
                            ),
                            metadata={
                                "shortfall_amount": round(shortfall, 2),
                                "projected_liquidity": round(projected_balance_in_hand, 2),
                                "category_to_cut": top_cat,
                                "items_to_cut": items_to_cut
                            }
                        ))
                else:
                    # Fallback if no specific "less important" category found
                    alerts.append(Alert(
                        agent=self.name,
                        type="liquidity",
                        severity="warning",
                        title="Low Liquidity for Upcoming Bills",
                        message=(
                            f"After regular extra spending, you'll be short of "
                            f"{essential_total - projected_balance_in_hand:,.0f} {currency} for upcoming bills."
                        ),
                        suggested_action="Try to reduce all non-essential spending immediately to ensure you can cover your rent and utilities.",
                        metadata={
                            "shortfall_amount": round(essential_total - projected_balance_in_hand, 2)
                        }
                    ))

        except Exception as e:
            log.error(f"LiquidityAgent error for {user_id}: {e}")
        return alerts
