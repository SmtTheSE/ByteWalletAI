"""
app/services/agent_runner.py

Phase 4: Orchestrates all proactive monitoring agents.

Runs all registered agents against the user's wallet snapshot,
deduplicates overlapping alerts, and returns a prioritised list.
"""
from __future__ import annotations
import logging
from typing import List

from app.agents.base_agent import Alert
from app.agents.subscription_agent import SubscriptionAgent
from app.agents.anomaly_agent import AnomalyAgent
from app.agents.savings_agent import SavingsAgent
from app.agents.liquidity_agent import LiquidityAgent
from app.agents.income_agent import IncomeAgent
from app.agents.goal_agent import GoalAgent

log = logging.getLogger("agent_runner")

# Registry of all active agents — add new agents here
_AGENTS = [
    SubscriptionAgent(),
    AnomalyAgent(),
    SavingsAgent(),
    LiquidityAgent(),
    IncomeAgent(),
    GoalAgent(),
]

# Severity ordering for deduplication priority
_SEVERITY_RANK = {"critical": 0, "warning": 1, "info": 2}


def run_all_agents(user_id: str, snapshot: dict) -> List[dict]:
    """
    Run all registered agents and return a deduplicated, prioritised list of alerts.

    Args:
        user_id:  The user identifier.
        snapshot: The wallet snapshot dict.

    Returns:
        List of alert dicts (sorted by severity: critical → warning → info).
    """
    all_alerts: List[Alert] = []

    for agent in _AGENTS:
        try:
            agent_alerts = agent.run(user_id, snapshot)
            all_alerts.extend(agent_alerts)
            log.info(f"Agent '{agent.name}' returned {len(agent_alerts)} alert(s)")
        except Exception as e:
            log.error(f"Agent '{agent.name}' crashed: {e}")

    # Deduplicate by (title, agent) to prevent duplicate alerts on re-runs
    seen = set()
    unique_alerts: List[Alert] = []
    for alert in all_alerts:
        key = (alert.agent, alert.title)
        if key not in seen:
            seen.add(key)
            unique_alerts.append(alert)

    # Sort: critical first, then warning, then info
    unique_alerts.sort(key=lambda a: _SEVERITY_RANK.get(a.severity, 99))

    return [
        {
            "agent":            a.agent,
            "type":             a.type,
            "severity":         a.severity,
            "title":            a.title,
            "message":          a.message,
            "suggested_action": a.suggested_action,
            "metadata":         a.metadata,
        }
        for a in unique_alerts
    ]
