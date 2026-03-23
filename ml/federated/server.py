"""
ml/federated/server.py

Phase 5: Federated Learning server — FedAvg aggregation.

Manages the global model version and aggregates weight updates
submitted by client simulations (individual user devices).

Key privacy guarantee: only model weight DELTAS (not raw data) are
ever transmitted. The server never sees a single transaction.

Usage (as part of FastAPI):
    from ml.federated.server import FedAvgServer, get_federated_server
    server = get_federated_server()
    server.submit_update(client_id, weight_delta, num_samples)
    global_weights = server.get_global_weights()
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import asyncio

import numpy as np

from app.config import settings

log = logging.getLogger("federated_server")

ROOT          = Path(__file__).parent.parent.parent
FED_MODEL_DIR = ROOT / "models" / "federated"
FED_MODEL_DIR.mkdir(parents=True, exist_ok=True)

GLOBAL_WEIGHTS_PATH = FED_MODEL_DIR / "global_weights.npz"
FED_METADATA_PATH   = FED_MODEL_DIR / "metadata.json"


@dataclass
class ClientUpdate:
    client_id:    str
    weight_delta: dict[str, np.ndarray]   # layer_name -> delta array
    num_samples:  int                     # Local sample count (used for weighted avg)
    submitted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AsyncFedAvgServer:
    """
    Federated Averaging (FedAvg) server with asyncio support.

    Collects weight deltas from clients and aggregates them using
    weighted averaging proportional to each client's sample count.
    Aggregation is triggered when `min_clients_to_aggregate` updates are queued.
    
    Uses asyncio.Lock instead of threading.Lock for FastAPI-native async.
    """

    def __init__(self, min_clients_to_aggregate: Optional[int] = None):
        self._lock = asyncio.Lock()
        self._pending_updates: list[ClientUpdate] = []
        self._global_weights: Optional[dict[str, np.ndarray]] = None
        self._version: int = 0
        self._min_clients = min_clients_to_aggregate or settings.fed_min_clients
        self._total_rounds = 0

        self._load_global_state()

    def _load_global_state(self):
        """Load persisted global weights from disk if available."""
        if GLOBAL_WEIGHTS_PATH.exists():
            try:
                data = np.load(str(GLOBAL_WEIGHTS_PATH), allow_pickle=True)
                self._global_weights = {k: data[k] for k in data.files}
                log.info(f"Loaded global federated weights ({len(self._global_weights)} layers)")
            except Exception as e:
                log.warning(f"Could not load global weights: {e}")

        if FED_METADATA_PATH.exists():
            try:
                meta = json.loads(FED_METADATA_PATH.read_text())
                self._version      = meta.get("version", 0)
                self._total_rounds = meta.get("total_rounds", 0)
                log.info(f"Federated model v{self._version}, {self._total_rounds} rounds")
            except Exception:
                pass

    def _save_global_state(self):
        """Persist global weights to disk."""
        if self._global_weights:
            np.savez(str(GLOBAL_WEIGHTS_PATH), **self._global_weights)
        FED_METADATA_PATH.write_text(json.dumps({
            "version":      self._version,
            "total_rounds": self._total_rounds,
            "updated_at":   datetime.now(timezone.utc).isoformat(),
        }))

    async def submit_update(
        self,
        client_id:    str,
        weight_delta: dict[str, list],
        num_samples:  int,
    ) -> dict:
        """
        Accept a weight delta from a client.
        Automatically aggregates when enough clients have submitted.

        Args:
            client_id:    Identifier of the submitting client.
            weight_delta: Dict of layer_name -> list (serialisable delta).
            num_samples:  Number of local training samples used.

        Returns:
            Status dict with version and whether aggregation occurred.
        """
        # Convert lists back to numpy arrays
        np_delta = {k: np.array(v) for k, v in weight_delta.items()}

        async with self._lock:
            self._pending_updates.append(ClientUpdate(
                client_id=client_id,
                weight_delta=np_delta,
                num_samples=num_samples,
            ))
            log.info(
                f"Received update from {client_id} "
                f"({num_samples} samples). Pending: {len(self._pending_updates)}/{self._min_clients}"
            )

            aggregated = False
            if len(self._pending_updates) >= self._min_clients:
                await self._aggregate()
                aggregated = True

        return {
            "accepted": True,
            "aggregated": aggregated,
            "global_model_version": self._version,
            "pending_updates": len(self._pending_updates),
        }

    async def _aggregate(self):
        """
        Perform FedAvg: weighted average of all pending weight deltas.
        Called internally when enough client updates are available.
        """
        total_samples = sum(u.num_samples for u in self._pending_updates)
        if total_samples == 0:
            self._pending_updates.clear()
            return

        # Collect all layer names across all updates
        layer_names = set()
        for u in self._pending_updates:
            layer_names.update(u.weight_delta.keys())

        aggregated: dict[str, np.ndarray] = {}
        for layer in layer_names:
            weighted_sum = None
            for u in self._pending_updates:
                if layer not in u.weight_delta:
                    continue
                weight = u.num_samples / total_samples
                delta  = u.weight_delta[layer] * weight
                weighted_sum = delta if weighted_sum is None else weighted_sum + delta

            if weighted_sum is not None:
                # Apply delta to current global weights (or initialise)
                current = (self._global_weights or {}).get(layer, np.zeros_like(weighted_sum))
                aggregated[layer] = current + weighted_sum

        self._global_weights = aggregated
        self._pending_updates.clear()
        self._version      += 1
        self._total_rounds += 1
        self._save_global_state()

        log.info(
            f"FedAvg aggregation complete — global model v{self._version} "
            f"({self._total_rounds} rounds total)"
        )

    def get_global_weights(self) -> dict:
        """Return current global weights as JSON-serialisable dict."""
        if not self._global_weights:
            return {}
        return {k: v.tolist() for k, v in self._global_weights.items()}

    def get_status(self) -> dict:
        return {
            "global_model_version": self._version,
            "total_rounds":         self._total_rounds,
            "pending_updates":      len(self._pending_updates),
            "min_clients":          self._min_clients,
            "layers_tracked":       list((self._global_weights or {}).keys()),
        }


#  Backwards-compatible synchronous wrapper  #

class FedAvgServer:
    """Legacy synchronous wrapper for AsyncFedAvgServer."""
    
    def __init__(self, min_clients_to_aggregate: int = 3):
        self._async_server = AsyncFedAvgServer(min_clients_to_aggregate)
    
    def submit_update(self, client_id: str, weight_delta: dict, num_samples: int) -> dict:
        """Synchronous wrapper for async submit."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context, need to use asyncio.run_coroutine_threadsafe
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        self._async_server.submit_update(client_id, weight_delta, num_samples)
                    )
                    return future.result()
            else:
                return loop.run_until_complete(
                    self._async_server.submit_update(client_id, weight_delta, num_samples)
                )
        except RuntimeError:
            # No event loop, create one
            return asyncio.run(
                self._async_server.submit_update(client_id, weight_delta, num_samples)
            )
    
    def get_global_weights(self) -> dict:
        return self._async_server.get_global_weights()
    
    def get_status(self) -> dict:
        return self._async_server.get_status()


#  Singleton  #

_server: Optional[FedAvgServer] = None


def get_federated_server() -> FedAvgServer:
    """Return the singleton FedAvgServer instance."""
    global _server
    if _server is None:
        _server = FedAvgServer(min_clients_to_aggregate=settings.fed_min_clients)
    return _server
