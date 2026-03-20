"""
app/services/messaging_service.py

Rule-based message generation for ByteWallet AI.
Produces a short, youth-friendly financial coaching message (max ~50 words).

All data is handled locally via deterministic math rules.
"""
import asyncio
import logging
import re
from typing import Tuple

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

def generate_ai_message(
    nickname: str | None,
    currency: str,
    stats: dict,
    snapshot: dict | None = None,
    mode: str = "rules_only",
) -> Tuple[str, str]:
    """
    Generate a dynamic coaching message for the user based on mathematical analytics
    and optional regex-driven pattern matching.
    """
    name = nickname or "friend"
    risk = stats.get("risk_level", "medium")
    
    # Gather Key Metrics (Existing Schema Fields)
    top_cat_list = stats.get("top_risky_categories", [])
    cat_name = top_cat_list[0]["category"] if top_cat_list else "non-essentials"
    cat_proj = top_cat_list[0]["projected_spent"] if top_cat_list else 0
    
    overshoot_pct = stats.get("budget_overshoot_percent", 0) * 100
    shortfall = stats.get("predicted_month_end_balance", 0)
    
    # Optional Regex-powered "Smart Advice"
    pattern_advice = _get_pattern_advice(snapshot) if snapshot else None

    if risk == "high":
        preamble = f"Hey {name}, your spending velocity is currently too high. "
        if shortfall < 0:
            insight = f"At this pace, you'll be {abs(shortfall):,.0f} {currency} short for your obligations by month-end. "
        else:
            insight = f"You are projected to overshoot your budget by {overshoot_pct:.1f}%. "
        
        # Use regex advice if found, else generic category advice
        action = pattern_advice if pattern_advice else f"Try cutting your {cat_name} spending immediately to stay safe."
        msg = f"{preamble}{insight}{action}"
        
    elif risk == "medium":
        preamble = f"Hey {name}, you're doing okay, but your {cat_name} spending is trending higher than usual. "
        # Prioritize regex advice if available
        insight = pattern_advice if pattern_advice else f"Reducing this category by just 15% could save you around {cat_proj * 0.15:,.0f} {currency} this month. "
        action = "A small pause now prevents a big squeeze later!"
        msg = f"{preamble}{insight} {action}"
        
    else:
        preamble = f"Excellent work, {name}! You're well within your limits. "
        insight = "Your current burn-rate is perfectly balanced. "
        action = "Consider moving a small extra amount to your savings today while you're ahead."
        msg = f"{preamble}{insight}{action}"

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
) -> Tuple[str, str]:
    """
    Hybrid Proactive Messaging (Custom ML + Ollama + Regex Rules).
    Logic Flow:
    1. Custom ML Model detects high risk.
    2. Ollama (Local LLM) generates a hyper-personalized actionable tip (Quick 10s timeout).
    3. Mathematical Rules + Regex Patterns provide instant deterministic fallback.
    """
    risk_level = stats.get("risk_level", "medium")

    if mode == "rules_only" or risk_level != "high":
        return generate_ai_message(nickname, currency, stats, snapshot, mode)

    name = nickname or "friend"
    top_cat = stats.get("top_risky_categories", [])
    cat_name = top_cat[0]["category"] if top_cat else "non-essentials"
    cat_spend = top_cat[0]["projected_spent"] if top_cat else 0

    spend_mtd = stats.get("spend_mtd", 0)
    banking_bal = snapshot.get("balances", {}).get("banking", 0)
    cash_bal = snapshot.get("balances", {}).get("cash", 0)
    total_balance = banking_bal + cash_bal

    # Context about upcoming obligations
    obligations = snapshot.get("essential_obligations", [])
    obs_text = ", ".join([f"{o['name']}: {o['amount']} {currency} ({o['due_date']})" for o in obligations])
    if not obs_text: obs_text = "No fixed obligations recorded."

    prompt = (
        f"You are ByteWallet AI, a local financial coach. User '{name}' spent {spend_mtd} {currency} this month. "
        f"Balance: {total_balance} {currency}. Bills: {obs_text}. "
        f"Top problem: {cat_name} (Projected: {cat_spend} {currency}).\n\n"
        f"Task: Generate a friendly 2-sentence warning to '{name}' "
        f"with one specific numerical suggestion to save money on {cat_name}. "
        f"No markdown, no emojis. Be direct and local-only."
    )

    # 1. Primary: Local Ollama (Fast 10s timeout)
    res = await generate_smart_ai_message_ollama(prompt)
    if res:
        return res, "ollama"

    # 2. Final Fallback: Traditional Rules + Regex Patterns
    return generate_ai_message(nickname, currency, stats, snapshot, mode)
