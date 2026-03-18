"""
app/api.py

FastAPI route definitions — POST /v1/predict-burn-rate
"""
import calendar
import logging
from datetime import datetime, timezone

from fastapi import APIRouter

from app.schemas import PredictBurnRateRequest, PredictBurnRateResponse, RiskyCategory, TriggerRuleFlags
from app.services import ml_service, rules, llm_service
from app.config import settings

log = logging.getLogger("api")
router = APIRouter()


@router.post("/v1/predict-burn-rate", response_model=PredictBurnRateResponse)
async def predict_burn_rate(payload: PredictBurnRateRequest):
    """
    Predict financial burn-rate risk for a given user.

    Steps:
      1. Convert payload → snapshot dict
      2. Run ML inference (or rule fallback)
      3. Apply 15th/65% business rule
      4. Determine final risk level
      5. Generate message via Rules engine
      6. Assemble and return response
    """
    # ── 1. Snapshot dict ──────────────────────────────────────────────────────
    snapshot = payload.model_dump()

    # ── 2. ML inference ───────────────────────────────────────────────────────
    stats = ml_service.run_prediction(snapshot)

    # ── 3. Business rules ─────────────────────────────────────────────────────
    current_date  = datetime.fromisoformat(payload.current_date)
    days_in_month = calendar.monthrange(current_date.year, current_date.month)[1]

    rule_result = rules.evaluate_rules(
        day_of_month  = current_date.day,
        days_in_month = days_in_month,
        spend_mtd     = stats["spend_mtd"],
        budget_total  = stats["budget_total"],
    )

    # ── 4. Final risk level ───────────────────────────────────────────────────
    risk_level = rules.determine_risk_level(
        shortfall_prob           = stats["shortfall_prob"],
        budget_overshoot_percent = stats["budget_overshoot_percent"],
        rule_result              = rule_result,
    )
    stats["risk_level"]   = risk_level
    stats["trigger_rule"] = rule_result.trigger_rule

    # ── 5. Resolve effective AI mode ──────────────────────────────────────────
    effective_mode = payload.ai_mode
    if effective_mode == "auto":
        effective_mode = settings.ai_default_mode   # "local_only" or "rules_only"

    # ── 6. Generate AI message via Rules Engine ───────────────────────────────
    ai_message, ai_mode_used = await llm_service.generate_ai_message(
        nickname = payload.nickname,
        currency = payload.currency,
        stats    = stats,
        mode     = effective_mode,
    )

    # ── 7. Assemble response ──────────────────────────────────────────────────
    trigger_flags = TriggerRuleFlags(
        day_fraction               = rule_result.day_fraction,
        budget_used_percent        = rule_result.budget_used_percent,
        hit_15th_65_percent_rule   = rule_result.hit_15th_65_percent_rule,
    )

    risky_cats = [RiskyCategory(**c) for c in stats.get("top_risky_categories", [])]

    return PredictBurnRateResponse(
        user_id                      = payload.user_id,
        currency                     = payload.currency,
        risk_level                   = risk_level,
        shortfall_prob               = stats["shortfall_prob"],
        predicted_month_end_balance  = stats["predicted_month_end_balance"],
        predicted_total_spend        = stats["predicted_total_spend"],
        budget_total                 = stats["budget_total"],
        budget_overshoot_amount      = stats["budget_overshoot_amount"],
        budget_overshoot_percent     = stats["budget_overshoot_percent"],
        trigger_rule                 = rule_result.trigger_rule,
        trigger_rule_flags           = trigger_flags,
        top_risky_categories         = risky_cats,
        ai_message                   = ai_message,
        ai_mode_used                 = ai_mode_used,
        generated_at                 = datetime.now(timezone.utc),
    )
