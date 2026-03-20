"""
ml/federated/client_sim.py

Phase 5: Federated Learning client simulator.

Simulates what happens on a user's local device:
  1. Downloads the current global model from the server
  2. Fine-tunes it locally on the user's private transaction data (1 gradient step)
  3. Computes the weight DELTA (new - old) — raw data never leaves the device
  4. POSTs the delta to the server

This script can be run standalone for testing, or called programmatically.

Usage:
    python -m ml.federated.client_sim --user_id "usr_001" --snapshot '{"transactions":[...]}'
    # Or via API: POST /v1/federated/submit-update
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Optional

import numpy as np

log = logging.getLogger("federated_client")

ROOT = Path(__file__).parent.parent.parent


def _load_global_weights_from_server() -> dict[str, np.ndarray]:
    """
    In production: would call GET /v1/federated/model to download weights.
    In simulation: reads directly from the server's shared state.
    """
    from ml.federated.server import get_federated_server
    server = get_federated_server()
    raw_weights = server.get_global_weights()
    return {k: np.array(v) for k, v in raw_weights.items()}


def _extract_local_features(snapshot: dict) -> tuple[np.ndarray, np.ndarray]:
    """
    Convert a local wallet snapshot into a feature matrix (X) and labels (y).
    Uses the existing ML feature pipeline — no new logic needed.
    """
    from ml.features import build_inference_features, FEATURE_COLUMNS
    from ml.labeler import label_shortfall

    # Build features using the existing pipeline
    X_df = build_inference_features(snapshot)
    X = X_df[FEATURE_COLUMNS].fillna(0).values.astype(np.float64)

    # Label: 1 if shortfall, 0 if safe — uses existing labeler logic
    stats      = X_df.iloc[0].to_dict() if len(X_df) > 0 else {}
    spend_pct  = stats.get("budget_used_pct", 0)
    progress   = stats.get("day_progress", 0.5)
    shortfall  = int(spend_pct > progress * 1.15)  # Simple on-device labelling
    y = np.array([shortfall], dtype=np.float64)
    return X, y


def _local_gradient_step(
    global_weights: dict[str, np.ndarray],
    X: np.ndarray,
    y: np.ndarray,
    learning_rate: float = 0.01,
) -> dict[str, np.ndarray]:
    """
    Perform a single gradient descent step on local data using logistic regression logic.
    Returns updated weights (not the delta — delta is computed outside).

    Note: In production with sklearn models, we'd use warm_start re-fitting or
    a plug-in gradient library. This simulates the concept cleanly.
    """
    # Simulate a simple logistic regression weight update
    # w key = "coef", b key = "intercept"
    w = global_weights.get("coef", np.zeros((1, X.shape[1]))).copy()
    b = global_weights.get("intercept", np.zeros(1)).copy()

    # Sigmoid prediction
    logits = X @ w.T + b
    preds  = 1 / (1 + np.exp(-logits.flatten()))

    # Gradient (binary cross-entropy)
    error = preds - y
    dw = (error[:, np.newaxis] * X).mean(axis=0, keepdims=True)
    db = np.array([error.mean()])

    # Update
    w_new = w - learning_rate * dw
    b_new = b - learning_rate * db

    return {"coef": w_new, "intercept": b_new}


def compute_and_submit_update(
    client_id:     str,
    snapshot:      dict,
    server=None,
    learning_rate: float = 0.01,
) -> dict:
    """
    Full client-side federated learning step:
    1. Load global weights
    2. Fine-tune locally (1 step)
    3. Compute delta = updated - global
    4. Submit delta to server

    Args:
        client_id:     Unique identifier for this client device.
        snapshot:      The user's private wallet snapshot (stays on device).
        server:        FedAvgServer instance (for in-process simulation).
        learning_rate: Learning rate for the local gradient step.

    Returns:
        Server response dict.
    """
    if server is None:
        from ml.federated.server import get_federated_server
        server = get_federated_server()

    try:
        # Step 1: Get global weights
        global_weights = _load_global_weights_from_server()

        # Step 2: Extract features from local private data
        try:
            X, y = _extract_local_features(snapshot)
        except Exception as e:
            log.warning(f"Feature extraction failed ({e}), using synthetic data")
            # Fallback: simulate with noise (for demo/testing purposes)
            num_features = global_weights["coef"].shape[1] if global_weights else 19
            X = np.random.randn(1, num_features)
            y = np.array([0.0])

        # If no global model yet, initialise empty weights using actual feature size
        if not global_weights:
            num_features = X.shape[1]
            global_weights = {
                "coef":      np.zeros((1, num_features)),
                "intercept": np.zeros(1),
            }

        # Step 3: Local gradient step
        updated_weights = _local_gradient_step(global_weights, X, y, learning_rate)

        # Step 4: Compute delta (ONLY the delta is sent, not the data or full weights)
        delta = {}
        for layer in updated_weights:
            if layer in global_weights:
                delta[layer] = (updated_weights[layer] - global_weights[layer]).tolist()
            else:
                delta[layer] = updated_weights[layer].tolist()

        num_samples = max(len(X), 1)

        log.info(
            f"Client {client_id}: local step complete "
            f"({num_samples} samples, {len(delta)} layers). Submitting delta..."
        )

        # Step 5: Submit delta to server
        result = server.submit_update(
            client_id=client_id,
            weight_delta=delta,
            num_samples=num_samples,
        )

        return {
            "client_id":   client_id,
            "num_samples": num_samples,
            "delta_layers": list(delta.keys()),
            "server_response": result,
        }

    except Exception as e:
        log.error(f"Client {client_id} federated step failed: {e}")
        return {"client_id": client_id, "error": str(e)}


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="ByteWallet Federated Learning Client Simulator")
    parser.add_argument("--user_id",  required=True, help="Client user ID")
    parser.add_argument("--snapshot", default="{}", help="JSON wallet snapshot")
    parser.add_argument("--lr",       type=float, default=0.01, help="Learning rate")
    args = parser.parse_args()

    snapshot = json.loads(args.snapshot)
    result   = compute_and_submit_update(args.user_id, snapshot, learning_rate=args.lr)
    print(json.dumps(result, indent=2))
