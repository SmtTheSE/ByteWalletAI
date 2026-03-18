"""
app/services/messaging_service.py

Rule-based message generation for ByteWallet AI.
Produces a short, youth-friendly financial coaching message (max ~50 words).

All data is handled locally via deterministic math rules.
"""
import logging
from typing import Tuple

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
