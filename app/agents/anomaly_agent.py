"""
app/agents/anomaly_agent.py

Phase 4: Detects financial anomalies in transaction history.
Detects:
  - Duplicate transactions (same merchant, same amount, same day)
  - Unusually large single transactions (> 2.5σ from user daily average)
"""
from __future__ import annotations
import logging
from typing import List

import numpy as np
import pandas as pd

from app.agents.base_agent import BaseAgent, Alert

log = logging.getLogger("anomaly_agent")


class AnomalyAgent(BaseAgent):
    name = "anomaly_agent"

    def run(self, user_id: str, snapshot: dict) -> List[Alert]:
        alerts: List[Alert] = []
        try:
            raw_txs = snapshot.get("transactions", []) or []
            currency = snapshot.get("currency", "VND")
            rows = []
            for t in raw_txs:
                if not isinstance(t, dict):
                    t = t.__dict__ if hasattr(t, "__dict__") else {}
                ts   = pd.to_datetime(t.get("timestamp", ""), utc=True, errors="coerce")
                amt  = abs(float(t.get("amount", 0)))
                note = str(t.get("note") or t.get("merchant_name") or t.get("category", ""))
                typ  = str(t.get("type", "expense")).lower()
                rows.append({"ts": ts, "amount": amt, "note": note.lower().strip(), "type": typ})

            if not rows:
                return alerts

            df = pd.DataFrame(rows)
            expenses = df[df["type"] == "expense"].copy()
            if expenses.empty:
                return alerts

            expenses["date"] = expenses["ts"].dt.date

            #  1. Duplicate detection 
            dup_key = expenses.groupby(["date", "note", "amount"]).size().reset_index(name="count")
            duplicates = dup_key[dup_key["count"] > 1]
            for _, row in duplicates.iterrows():
                alerts.append(Alert(
                    agent=self.name,
                    type="anomaly",
                    severity="warning",
                    title=f"Possible duplicate charge: {row['note']}",
                    message=(
                        f"A charge of {row['amount']:,.0f} {currency} from '{row['note']}' "
                        f"appeared {int(row['count'])} times on {row['date']}. "
                        f"This may be a duplicate transaction."
                    ),
                    suggested_action=(
                        "Check with the merchant or your bank to confirm whether "
                        "you were charged multiple times."
                    ),
                    metadata={
                        "merchant": row["note"],
                        "date":     str(row["date"]),
                        "amount":   row["amount"],
                        "count":    int(row["count"]),
                    },
                ))

            #  2. Unusually large transaction detection 
            if len(expenses) >= 5:
                mean_amt = expenses["amount"].mean()
                std_amt  = expenses["amount"].std()
                threshold = mean_amt + 2.5 * std_amt

                outliers = expenses[expenses["amount"] > threshold]
                for _, row in outliers.iterrows():
                    alerts.append(Alert(
                        agent=self.name,
                        type="anomaly",
                        severity="info",
                        title=f"Unusually large transaction: {row['note']}",
                        message=(
                            f"A transaction of {row['amount']:,.0f} {currency} from '{row['note']}' "
                            f"is significantly higher than the usual average of {mean_amt:,.0f} {currency}."
                        ),
                        suggested_action=(
                            "Verify this charge is expected. "
                            "If not, contact your bank immediately."
                        ),
                        metadata={
                            "merchant":  row["note"],
                            "amount":    row["amount"],
                            "avg":       round(mean_amt, 2),
                            "threshold": round(threshold, 2),
                        },
                    ))

        except Exception as e:
            log.error(f"AnomalyAgent error for {user_id}: {e}")
        return alerts
