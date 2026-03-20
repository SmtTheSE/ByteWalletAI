"""
app/services/messaging_service.py

Rule-based message generation for ByteWallet AI.
Produces a short, youth-friendly financial coaching message (max ~50 words).

All data is handled locally via deterministic math rules.
"""
import logging
from typing import Tuple

import google.genai as genai
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

async def generate_smart_ai_message(
    snapshot: dict,
    stats: dict,
    rule_result,
    nickname: str | None,
    currency: str,
    mode: str = "auto",
) -> Tuple[str, str]:
    """
    Advanced LLM-driven messaging. 
    Constructs a dynamic context containing exact spend pace, obligations, and balances,
    then requests a hyper-personalized 2-sentence actionable nudge from Gemini.
    Falls back to `generate_ai_message` if the LLM fails or API key is absent.
    """
    api_key = settings.gemini_api_key
    if not api_key or mode == "rules_only":
        return generate_ai_message(nickname, currency, stats, mode)

    name = nickname or "friend"
    top_cat = stats.get("top_risky_categories", [])
    cat_name = top_cat[0]["category"] if top_cat else "non-essentials"
    cat_spend = top_cat[0]["projected_spent"] if top_cat else 0

    spend_mtd = stats.get("spend_mtd", 0)
    banking_bal = snapshot.get("balances", {}).get("banking", 0)
    cash_bal = snapshot.get("balances", {}).get("cash", 0)
    total_balance = banking_bal + cash_bal

    # Summarise upcoming obligations
    obligations = snapshot.get("essential_obligations", [])
    obs_text = ", ".join([f"{o['name']} of {o['amount']} {currency} due {o['due_date']}" for o in obligations])
    if not obs_text:
        obs_text = "No fixed obligations recorded."

    prompt = (
        f"You are ByteWallet AI. The user '{name}' spent {spend_mtd} {currency} the current month to date. "
        f"Their remaining total balance is {total_balance} {currency}. "
        f"Upcoming obligations: {obs_text}. "
        f"Top spending category is: {cat_name} (Projected: {cat_spend} {currency}).\n\n"
        f"Task: Generate a friendly, warning-style message (maximum 2 sentences) directly addressing '{name}' "
        f"with a specific, numerical, highly actionable cutback suggestion to prevent a financial shortfall. "
        f"Do not use markdown formatting or emojis. Keep it extremely concise and human."
    )

    try:
        client = genai.Client(api_key=api_key)
        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        if response.text:
            return response.text.strip(), "gemini"
    except Exception as e:
        log.error(f"Gemini LLM messaging failed ({e}), falling back to rules.")

    return generate_ai_message(nickname, currency, stats, mode)
