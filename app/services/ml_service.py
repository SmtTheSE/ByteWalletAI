"""
app/services/ml_service.py

Thin wrapper around ml/inference_core.py — used by the API router.
Handles model loading on startup (shared state via module-level object).
"""
import logging
from ml.inference_core import predict_burn_risk_from_snapshot, _load_model

log = logging.getLogger("ml_service")


def preload_model():
    """Call once at startup to load model into memory."""
    model = _load_model()
    if model is None:
        log.warning(
            "Trained model not found. API will use rule-based fallback.\n"
            "To train the model run:  python -m ml.train_model"
        )
    else:
        log.info("ML model loaded successfully ")


def run_prediction(snapshot: dict) -> dict:
    """
    Run the burn-rate prediction for a given user snapshot.

    Args:
        snapshot: dict matching PredictBurnRateRequest fields

    Returns:
        dict matching PredictBurnRateResponse fields (without ai_message)
    """
    return predict_burn_risk_from_snapshot(snapshot)
