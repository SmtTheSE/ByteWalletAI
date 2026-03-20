"""
app/services/messaging_service.py

Rule-based message generation for ByteWallet AI.
Produces a short, youth-friendly financial coaching message (max ~50 words).

All data is handled locally via deterministic math rules.
"""
import asyncio
import logging
from typing import Tuple

import httpx
from app.config import settings

log = logging.getLogger("messaging_service")

def generate_ai_message(
    nickname: str | None,
    currency: str,
    stats: dict,
    mode: str = "rules_only",
) -> Tuple[str, str]:
    """
    Generate a coaching message for the user based strictly on mathematical rules.
    Used as the absolute baseline fallback if Ollama is unavailable.
    """
    name     = nickname or "friend"
    risk     = stats.get("risk_level", "medium")
    top_cat  = stats.get("top_risky_categories", [])
    cat_name = top_cat[0]["category"] if top_cat else "non-essentials"

    if risk == "high":
        msg = (
            f"Hey {name}, your spending pace is putting you at risk of hitting your budget limit. "
            f"Your biggest category is {cat_name} — try cutting it by 20% this week. "
            f"Small changes today = less stress at month-end."
        )
    elif risk == "medium":
        msg = (
            f"Hey {name}, you're on track but spending a bit faster than planned. "
            f"Watch your {cat_name} spending for the next few days. "
            f"A tiny pause before non-essential purchases can make a big difference."
        )
    else:
        msg = (
            f"Great job, {name}! Your spending is well within budget this month. "
            f"Keep it up and you might hit your savings goal early. "
            f"Consider moving a little extra to savings today while you're ahead!"
        )
    return msg, "rules_only"

async def generate_smart_ai_message_ollama(prompt: str) -> str | None:
    """
    Generate a message using a local Ollama instance via its REST API.
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
    Hybrid Proactive Messaging (Custom ML + Ollama).
    Logic Flow:
    1. Custom ML Model detects high risk.
    2. Ollama (Local LLM) generates a hyper-personalized actionable tip.
    3. Mathematical Rules provide instant deterministic fallback.
    """
    risk_level = stats.get("risk_level", "medium")

    # -------------------------------------------------------------
    # 🎯 ARCHITECTURE ALIGNMENT: The Gemini-Free Hybrid Flow
    # -------------------------------------------------------------
    # Rule D --> |Within Safety| F[End Flow/Local Rule Generation]
    # Rule D --> |Above Budget| E[Send to local Ollama Voice Engine]
    # -------------------------------------------------------------
    if mode == "rules_only" or risk_level != "high":
        return generate_ai_message(nickname, currency, stats, mode)

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

    # 1. Primary: Local Ollama
    res = await generate_smart_ai_message_ollama(prompt)
    if res:
        return res, "ollama"

    # 2. Final Fallback: Traditional Rules
    return generate_ai_message(nickname, currency, stats, mode)
