"""
app/services/rag_service.py

Phase 2: RAG (Retrieval-Augmented Generation) service.

Converts raw wallet transactions into searchable text documents,
indexes them in the local ChromaDB vector store, and retrieves
relevant context to ground the Gemini LLM's answers in real history.

Key design principle: all data stays on the local machine.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from app.db.vector_store import upsert_user_transactions, query_similar
from app.config import settings

log = logging.getLogger("rag_service")


def _transaction_to_text(tx: dict) -> str:
    """
    Convert a raw transaction dict into a human-readable text document
    optimised for semantic search.

    Example output:
      "2026-03-10 | Tuesday | expense | Food | 150,000 VND | Highland Coffee | cash"
    """
    import pandas as pd
    ts = tx.get("timestamp", "")
    try:
        dt = pd.to_datetime(ts, utc=True)
        date_str = dt.strftime("%Y-%m-%d")
        day_str  = dt.strftime("%A")  # "Monday", "Tuesday", etc.
    except Exception:
        date_str = str(ts)[:10]
        day_str  = ""

    amount   = tx.get("amount", 0)
    category = tx.get("category", "Unknown")
    tx_type  = tx.get("type", "expense")
    note     = tx.get("note") or tx.get("merchant_name") or ""
    payment  = tx.get("payment_method") or ""

    parts = [date_str, day_str, tx_type, category, f"{amount:,.0f}", note, payment]
    return " | ".join(p for p in parts if p)


def _build_tx_id(user_id: str, tx: dict) -> str:
    """Build a deterministic unique ID for a transaction document."""
    ts  = str(tx.get("timestamp", ""))[:19]
    amt = str(tx.get("amount", 0))
    cat = str(tx.get("category", ""))
    return f"{user_id}_{ts}_{amt}_{cat}".replace(" ", "_").replace(":", "-")


def index_transactions(user_id: str, transactions: list[dict]) -> int:
    """
    Index all transactions for a user into the vector store.
    Should be called at the start of a /v1/chat request or on data update.

    Args:
        user_id:      The user identifier.
        transactions: List of raw transaction dicts from the wallet snapshot.

    Returns:
        Number of documents indexed.
    """
    if not transactions:
        return 0

    documents = []
    for tx in transactions:
        if not isinstance(tx, dict):
            tx = tx.__dict__ if hasattr(tx, "__dict__") else {}
        
        text = _transaction_to_text(tx)
        doc_id = _build_tx_id(user_id, tx)
        metadata = {
            "category":       str(tx.get("category", "")),
            "amount":         float(tx.get("amount", 0)),
            "type":           str(tx.get("type", "expense")),
            "timestamp":      str(tx.get("timestamp", ""))[:19],
            "payment_method": str(tx.get("payment_method") or ""),
        }
        documents.append({"id": doc_id, "text": text, "metadata": metadata})

    return upsert_user_transactions(user_id, documents)


def retrieve_context(user_id: str, question: str) -> Optional[str]:
    """
    Retrieve the most relevant historical transactions for a given question.

    Returns:
        A formatted string of relevant transactions to inject into the LLM prompt,
        or None if RAG is disabled or no results found.
    """
    if not settings.rag_enabled:
        return None

    results = query_similar(user_id, question, top_k=settings.rag_top_k)
    if not results:
        return None

    lines = ["Most relevant past transactions from the user's history:"]
    for i, r in enumerate(results, 1):
        lines.append(f"  {i}. {r['text']}")

    return "\n".join(lines)


async def index_and_retrieve(
    user_id: str,
    transactions: list[dict],
    question: str,
) -> Optional[str]:
    """
    Convenience function: index transactions first, then retrieve context.
    Called from the /v1/chat endpoint before invoking the LLM.
    """
    indexed = index_transactions(user_id, transactions)
    log.info(f"Indexed {indexed} transactions for user {user_id}")
    return retrieve_context(user_id, question)
