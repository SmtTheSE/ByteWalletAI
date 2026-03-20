"""
app/api.py

FastAPI route definitions:
  - POST /v1/predict-burn-rate   — ML burn-rate prediction
  - POST /v1/chat                — Phase 1: NL Function Calling (Gemini)
"""
import calendar
import logging
from datetime import datetime, timezone

from fastapi import APIRouter

from app.schemas import (
    PredictBurnRateRequest, PredictBurnRateResponse, RiskyCategory, TriggerRuleFlags,
    ProactiveAlert,
)
from app.services import ml_service, rules, messaging_service
from app.services.agent_runner import run_all_agents
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
    #  1. Snapshot dict 
    snapshot = payload.model_dump()

    #  2. ML inference 
    stats = ml_service.run_prediction(snapshot)

    #  3. Business rules 
    current_date  = datetime.fromisoformat(payload.current_date)
    days_in_month = calendar.monthrange(current_date.year, current_date.month)[1]

    rule_result = rules.evaluate_rules(
        day_of_month  = current_date.day,
        days_in_month = days_in_month,
        spend_mtd     = stats["spend_mtd"],
        budget_total  = stats["budget_total"],
    )

    #  4. Final risk level (Adaptive Math + Rules)
    risk_level = rules.determine_risk_level(
        shortfall_prob           = stats["shortfall_prob"],
        budget_overshoot_percent = stats["budget_overshoot_percent"],
        rule_result              = rule_result,
        predicted_balance        = stats["predicted_month_end_balance"],
    )
    stats["risk_level"]   = risk_level
    stats["trigger_rule"] = rule_result.trigger_rule

    #  5. Resolve effective AI mode 
    effective_mode = payload.ai_mode
    if effective_mode == "auto":
        effective_mode = settings.ai_default_mode   # "local_only" or "rules_only"

    # 6. Messaging rules (Smart LLM + Rules Fallback)
    ai_message, ai_mode_used = await messaging_service.generate_smart_ai_message(
        snapshot=snapshot,
        stats=stats,
        rule_result=rule_result,
        nickname=payload.nickname,
        currency=payload.currency,
        mode=effective_mode,
    )

    #  7. Assemble response 
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
        proactive_alerts             = [ProactiveAlert(**a) for a in run_all_agents(payload.user_id, snapshot)],
        generated_at                 = datetime.now(timezone.utc),
    )


#  Phase 5: Federated Learning 

@router.get("/v1/federated/model", tags=["federated"])
async def get_federated_model():
    """
    Download the current global federated model weights.
    Clients call this before local training to get the latest global model.
    """
    from ml.federated.server import get_federated_server
    server = get_federated_server()
    return {
        "status":      "ok",
        "model_info":  server.get_status(),
        "weights":     server.get_global_weights(),
    }


@router.post("/v1/federated/submit-update", tags=["federated"])
async def submit_federated_update(payload: dict):
    """
    Accept a weight delta from a client device.

    Expected payload:
    {
        "client_id":    "usr_001_device_abc",
        "weight_delta": {"coef": [[...]], "intercept": [...]},
        "num_samples":  42
    }

    Raw transaction data is NEVER sent — only the mathematical delta.
    """
    from ml.federated.server import get_federated_server
    server = get_federated_server()

    client_id    = payload.get("client_id", "unknown")
    weight_delta = payload.get("weight_delta", {})
    num_samples  = int(payload.get("num_samples", 1))

    result = server.submit_update(
        client_id=client_id,
        weight_delta=weight_delta,
        num_samples=num_samples,
    )
    return {"status": "accepted", "result": result}

