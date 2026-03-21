"""
app/agents/goal_agent.py

Tracks user progress towards specific financial goals.
Expects a 'savings_goals' list in the snapshot metadata.
"""
from __future__ import annotations
import logging
from typing import List

from app.agents.base_agent import BaseAgent, Alert

log = logging.getLogger("goal_agent")

class GoalAgent(BaseAgent):
    name = "goal_agent"

    def run(self, user_id: str, snapshot: dict) -> List[Alert]:
        alerts: List[Alert] = []
        try:
            currency = snapshot.get("currency", "VND")
            
            # 1. Get current savings status
            balances = snapshot.get("balances", {})
            if hasattr(balances, "__dict__"):
                balances = balances.__dict__
            total_balance = float(balances.get("banking", 0)) + float(balances.get("cash", 0))

            # 2. Extract Goals (Expected format: [{ "name": "New Bike", "target": 10000000, "deadline": "2026-12-31" }])
            goals = snapshot.get("savings_goals", [])
            if not goals and "metadata" in snapshot:
                goals = snapshot.get("metadata", {}).get("savings_goals", [])

            if not goals:
                # If no specific goals, provide a generic "Emergency Fund" nudge if balance is low
                if total_balance < 1_000_000 and currency == "VND":
                     alerts.append(Alert(
                        agent=self.name,
                        type="savings",
                        severity="info",
                        title="Start a small safety fund.",
                        message="Having a small cash buffer helps avoid stress when unexpected bills arrive.",
                        suggested_action="Try setting a goal to save your first 2,000,000 VND this year."
                    ))
                return alerts

            for goal in goals:
                name = goal.get("name", "Goal")
                target = float(goal.get("target", 0))
                if target <= 0: continue

                progress_pct = (total_balance / target) * 100
                
                if progress_pct >= 100:
                    alerts.append(Alert(
                        agent=self.name,
                        type="savings",
                        severity="info",
                        title=f"Goal Reached: {name}!",
                        message=f"Congratulations! You've successfully saved {total_balance:,.0f} {currency} for your {name}.",
                        suggested_action="Consider finalizing your purchase or starting your next big goal today."
                    ))
                elif progress_pct > 80:
                    alerts.append(Alert(
                        agent=self.name,
                        type="savings",
                        severity="info",
                        title=f"Almost there with {name}!",
                        message=f"You are {progress_pct:.1f}% of the way to your {name} goal.",
                        suggested_action=f"Just {target - total_balance:,.0f} {currency} more to go. Keep it up!"
                    ))
                elif progress_pct < 20:
                     # New goal or lagging
                     alerts.append(Alert(
                        agent=self.name,
                        type="savings",
                        severity="info",
                        title=f"Getting started on {name}.",
                        message=f"Every small amount helps. You are currently at {progress_pct:.1f}% toward your {name} target.",
                        suggested_action="Try transferring a small amount today to build momentum."
                    ))

        except Exception as e:
            log.error(f"GoalAgent error for {user_id}: {e}")
        return alerts
