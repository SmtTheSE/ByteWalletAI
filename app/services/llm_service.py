"""
app/services/llm_service.py

Ollama-based LLM message generation for ByteWallet AI.
Produces a short, youth-friendly financial coaching message (max ~50 words).

Only Ollama (local) is used — no data leaves the device.
No PII (email, phone numbers) is ever sent to the LLM.
"""
import logging
from typing import Tuple

import httpx

from app.config import settings

log = logging.getLogger("llm_service")

# ─── Prompt templates ────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are ByteWallet's friendly AI money coach for students and young adults in Southeast Asia.
Your tone is warm, non-judgmental, and encouraging — like a smart friend, not a bank.
Always write in clear English. Keep your response to 2-3 short sentences maximum.
End with exactly ONE concrete, actionable suggestion (e.g., "Try skipping coffee shops for 3 days").
Never mention exact bank details, emails, or account numbers."""


def _build_user_prompt(nickname: str, currency: str, stats: dict) -> str:
    name        = nickname or "friend"
    progress_pct = int(stats.get("progress", 0) * 100)
    budget_pct   = int(stats.get("budget_used_pct", 0) * 100)
    spend        = _fmt(stats.get("spend_mtd", 0), currency)
    budget       = _fmt(stats.get("budget_total", 0), currency)
    overshoot    = _fmt(stats.get("budget_overshoot_amount", 0), currency)
    risk         = stats.get("risk_level", "medium")
    top_cat      = stats.get("top_risky_categories", [])
    top_cat_name = top_cat[0]["category"] if top_cat else "miscellaneous"
    top_cat_spent = _fmt(top_cat[0]["current_spent"] if top_cat else 0, currency)
    obligations  = _fmt(stats.get("essential_total", 0), currency)
    trigger      = stats.get("trigger_rule", None)

    trigger_line = (
        f"⚠️ You've already used {budget_pct}% of your budget in the first half of the month.\n"
        if trigger == "15th_65_percent" else ""
    )

    return f"""User: {name}
Month progress: {progress_pct}% of the month passed
Budget used: {budget_pct}% ({spend} out of {budget})
Risk level: {risk}
Top spending category: {top_cat_name} ({top_cat_spent} spent so far)
Essential obligations due: {obligations}
Projected overshoot: {overshoot}
{trigger_line}
Write a short, friendly 2-3 sentence coaching message for {name}. End with one specific action they can take today."""


def _fmt(amount: float, currency: str) -> str:
    """Format an amount with currency code and thousands separator."""
    if amount < 0:
        return f"-{currency} {abs(int(amount)):,}"
    return f"{currency} {int(amount):,}"


# ─── Ollama call ─────────────────────────────────────────────────────────────

async def _call_ollama(user_prompt: str) -> str:
    """Call local Ollama /api/chat endpoint."""
    payload = {
        "model":  settings.ollama_model,
        "stream": False,
        "messages": [
            {"role": "system",  "content": SYSTEM_PROMPT},
            {"role": "user",    "content": user_prompt},
        ],
        "options": {
            "temperature": 0.65,
            "num_predict": 120,
        },
    }
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(
            f"{settings.ollama_base_url}/api/chat",
            json=payload,
        )
        res.raise_for_status()
        data = res.json()
        return data["message"]["content"].strip()


# ─── Fallback template ───────────────────────────────────────────────────────

def _fallback_message(nickname: str, currency: str, stats: dict) -> Tuple[str, str]:
    """
    Rule-based template message when Ollama is unavailable.
    Returns (message, ai_mode_used).
    """
    name     = nickname or "there"
    risk     = stats.get("risk_level", "medium")
    overshoot = stats.get("budget_overshoot_amount", 0)
    top_cat  = stats.get("top_risky_categories", [])
    cat_name = top_cat[0]["category"] if top_cat else "non-essentials"

    if risk == "high":
        msg = (
            f"Hey {name}, your spending pace is putting you at risk of hitting your budget limit. "
            f"Your biggest category is {cat_name} — try cutting it by 20% this week. "
            f"Small changes today = less stress at month-end. 💪"
        )
    elif risk == "medium":
        msg = (
            f"Hey {name}, you're on track but spending a bit faster than planned. "
            f"Watch your {cat_name} spending for the next few days. "
            f"A tiny pause before non-essential purchases can make a big difference. 🎯"
        )
    else:
        msg = (
            f"Great job, {name}! Your spending is well within budget this month. "
            f"Keep it up and you might hit your savings goal early. "
            f"Consider moving a little extra to savings today while you're ahead! 🌟"
        )
    return msg, "rules_only"


# ─── Public function ──────────────────────────────────────────────────────────

async def generate_ai_message(
    nickname: str | None,
    currency: str,
    stats: dict,
    mode: str = "local_only",
) -> Tuple[str, str]:
    """
    Generate a coaching message for the user.

    Args:
        nickname: user's display name (optional)
        currency: ISO currency code (e.g. "VND")
        stats:    dict with keys: progress, budget_used_pct, spend_mtd,
                  budget_total, budget_overshoot_amount, risk_level,
                  top_risky_categories, essential_total, trigger_rule
        mode:     "local_only" | "rules_only"

    Returns:
        Tuple of (ai_message: str, ai_mode_used: str)
    """
    if mode == "rules_only":
        return _fallback_message(nickname, currency, stats)

    # local_only — Ollama
    user_prompt = _build_user_prompt(nickname or "friend", currency, stats)
    try:
        message = await _call_ollama(user_prompt)
        if not message:
            raise ValueError("Empty response from Ollama")
        return message, "local_ollama"
    except Exception as e:
        log.warning(f"Ollama call failed ({e}), using template fallback")
        return _fallback_message(nickname, currency, stats)
