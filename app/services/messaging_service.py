"""
app/services/messaging_service.py

Rule-based message generation for ByteWallet AI.
Produces a short, youth-friendly financial coaching message (max ~50 words).

All data is handled locally via deterministic math rules.
"""
import asyncio
import logging
import re
from typing import Tuple, List

import httpx
from app.config import settings

log = logging.getLogger("messaging_service")

# Smart Regex Patterns for localized youth coaching
SMART_PATTERNS = {
    r"(?i)(starbucks|highlands|cafe|coffee|drink|tea|milktea)": "Consider brewing at home for a few days to save costs.",
    r"(?i)(grab|ride|taxi|bolt|bike|gojek)": "Maybe consider the bus or a quick walk to stay under budget.",
    r"(?i)(netflix|spotify|youtube|premium|sub|hbo)": "Any subscriptions here you're not using? Canceling could provide instant relief.",
    r"(?i)(shopee|lazada|tiki|amazon|mall|order|shopping)": "Try waiting for the next big sale before making more impulse buys.",
}

def _get_pattern_advice(snapshot: dict) -> str | None:
    """Scan recent transactions for specific spending patterns via regex."""
    transactions = snapshot.get("transactions", [])
    # Look at last 10 transactions for patterns
    for tx in list(transactions)[-10:]:
        raw_text = f"{tx.get('note', '')} {tx.get('category', '')}".lower()
        for pattern, advice in SMART_PATTERNS.items():
            if re.search(pattern, raw_text):
                return advice
    return None

# Severity ordering for coaching priorities
_COACHING_PRIORITY = {
    # Urgent/Critical: Direct impact on living standards or security
    "liquidity":    0, 
    "anomaly":      1,
    # Warning/Important: Financial waste or late cashflow
    "income":       2,
    "subscription": 3,
    # Info/Optimization: Long term goals and idle cash
    "savings":      4,
    "goal":         5,
}

def generate_ai_message(
    nickname: str | None,
    currency: str,
    stats: dict,
    snapshot: dict | None = None,
    mode: str = "rules_only",
    proactive_alerts: List[dict] = None,
) -> Tuple[str, str]:
    """
    Generate a dynamic coaching message based on math rules, prioritized alerts,
    and optional regex-driven pattern matching.
    """
    name = nickname or "friend"
    risk = stats.get("risk_level", "medium")
    alerts = proactive_alerts or []
    
    # 1. Check for Critical Agent Alerts First (Condition-1, etc.)
    sorted_alerts = sorted(alerts, key=lambda a: _COACHING_PRIORITY.get(a["type"], 99))
    top_alert = sorted_alerts[0] if sorted_alerts else None
    
    # If we have a high-priority alert, use it as the core message
    if top_alert and (top_alert["severity"] in ("critical", "warning")):
        msg = f"Hey {name}, {top_alert['message']} {top_alert['suggested_action']}"
        return msg, "rules_only"

    # 2. Fallback to General Rules if no specific agent alert triggered
    top_cat_list = stats.get("top_risky_categories", [])
    cat_name = top_cat_list[0]["category"] if top_cat_list else "non-essentials"
    cat_proj = top_cat_list[0]["projected_spent"] if top_cat_list else 0
    overshoot_pct = stats.get("budget_overshoot_percent", 0) * 100
    shortfall = stats.get("predicted_month_end_balance", 0)
    
    pattern_advice = _get_pattern_advice(snapshot) if snapshot else None

    if risk == "high":
        preamble = f"Hey {name}, your spending velocity is currently too high. "
        insight = f"At this pace, you'll be {abs(shortfall):,.0f} {currency} short by month-end. " if shortfall < 0 else f"You'll overshoot your budget by {overshoot_pct:.1f}%. "
        action = pattern_advice if pattern_advice else f"Try cutting your {cat_name} spending immediately."
        msg = f"{preamble}{insight}{action}"
    elif risk == "medium":
        preamble = f"Hey {name}, you're doing okay, but your {cat_name} spending is trending high. "
        insight = pattern_advice if pattern_advice else f"Reducing this category by 15% could save you around {cat_proj * 0.15:,.0f} {currency}. "
        msg = f"{preamble}{insight}A small pause now prevents a big squeeze later!"
    else:
        # Check for Info alerts (Optimization)
        if top_alert:
            return f"Excellent work, {name}! {top_alert['message']}", "rules_only"
        msg = f"Excellent work, {name}! Your burn-rate is perfectly balanced. Consider moving extra cash to savings."

    return msg, "rules_only"

async def generate_smart_ai_message_ollama(prompt: str) -> str | None:
    """
    Generate a message using a local Ollama instance via its REST API.
    Fast timeout (10s) to reduce dependency as requested.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{settings.ollama_base_url}/api/generate",
                json={
                    "model": settings.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                }
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("response", "").strip()
    except Exception as e:
        log.error(f"Ollama local messaging failed ({e})")
    return None

async def generate_smart_ai_message(
    snapshot: dict,
    stats: dict,
    rule_result,
    nickname: str | None,
    currency: str,
    mode: str = "auto",
    proactive_alerts: List[dict] = None,
) -> Tuple[str, str]:
    """
    Universal Command & Coaching Brain (Custom ML + Multi-Agent Alerts + Ollama).
    Synthesizes signals from 6 specialized monitoring agents into one cohesive message.
    """
    risk_level = stats.get("risk_level", "medium")
    alerts = proactive_alerts or []

    if mode == "rules_only":
        return generate_ai_message(nickname, currency, stats, snapshot, mode, alerts)

    name = nickname or "friend"
    
    # Prioritize alerts for the LLM prompt
    sorted_alerts = sorted(alerts, key=lambda a: _COACHING_PRIORITY.get(a["type"], 99))
    top_issues = "; ".join([f"{a['title']}: {a['message']}" for a in sorted_alerts[:2]])
    
    spend_mtd = stats.get("spend_mtd", 0)
    banking_bal = snapshot.get("balances", {}).get("banking", 0)
    cash_bal = snapshot.get("balances", {}).get("cash", 0)
    total_balance = banking_bal + cash_bal

    obligations = snapshot.get("essential_obligations", [])
    obs_text = ", ".join([f"{o['name']}: {o['amount']} {currency}" for o in obligations]) or "None"

    # The AI Coach Prompt inherits all agent insights
    prompt = (
        f"You are ByteWallet AI, a local financial coach for ASEAN youth. Context for '{name}':\n"
        f"- Risk Level: {risk_level.upper()}\n"
        f"- Wallet: {total_balance} {currency} balance; {spend_mtd} spent this month.\n"
        f"- Bills: {obs_text}\n"
        f"- Intelligence Signals: {top_issues if top_issues else 'All systems green'}.\n\n"
        f"Task: Generate a friendly, supportive 2-sentence coaching tip. "
        f"Prioritize mentioning the most severe Intelligence Signal if it exists. "
        f"No markdown, no emojis. Be direct and local-only."
    )

    # 1. Primary: Local Ollama (Synthesizer)
    res = await generate_smart_ai_message_ollama(prompt)
    if res:
        return res, "ollama"

    # 2. Fallback: Prioritized Math Rules
    return generate_ai_message(nickname, currency, stats, snapshot, mode, alerts)
