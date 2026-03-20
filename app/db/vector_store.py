"""
app/db/vector_store.py

Phase 2: ChromaDB-backed vector store for RAG on transaction history.

Runs fully locally — no external server or cloud dependency.
Stores per-user transaction embeddings keyed by user_id.

Usage:
    from app.db.vector_store import upsert_user_transactions, query_similar

    upsert_user_transactions("user_123", [
        {"id": "tx_1", "text": "2026-03-10 | Food | 150000 VND | Highland Coffee", "metadata": {...}}
    ])

    results = query_similar("user_123", "coffee spending", top_k=5)
"""
from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger("vector_store")

# Lazy-initialized ChromaDB client (avoids slow import at startup if not used)
_chroma_client = None
_collections: dict[str, Any] = {}


def _get_client():
    global _chroma_client
    if _chroma_client is None:
        try:
            import chromadb
            # Persist to disk so embeddings survive restarts
            _chroma_client = chromadb.PersistentClient(path=".chroma_db")
            log.info("ChromaDB client initialized at .chroma_db")
        except ImportError:
            log.warning("chromadb not installed. RAG features will be disabled. Run: pip install chromadb")
            return None
    return _chroma_client


def _get_collection(user_id: str):
    """Get or create a per-user ChromaDB collection."""
    if user_id in _collections:
        return _collections[user_id]

    client = _get_client()
    if client is None:
        return None

    collection_name = f"user_{user_id.replace('-', '_')}"
    try:
        collection = client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},  # cosine similarity for semantic search
        )
        _collections[user_id] = collection
        return collection
    except Exception as e:
        log.error(f"Failed to get/create ChromaDB collection for {user_id}: {e}")
        return None


def upsert_user_transactions(user_id: str, tx_documents: list[dict]) -> int:
    """
    Insert or update transaction embeddings for a user.

    Args:
        user_id:        The user identifier.
        tx_documents:   List of dicts with keys:
                        - 'id':       unique string ID for the transaction
                        - 'text':     human-readable text of the transaction (will be embedded)
                        - 'metadata': dict of extra data (category, amount, date, etc.)

    Returns:
        Number of documents upserted.
    """
    collection = _get_collection(user_id)
    if collection is None:
        return 0

    if not tx_documents:
        return 0

    ids       = [d["id"] for d in tx_documents]
    documents = [d["text"] for d in tx_documents]
    metadatas = [d.get("metadata", {}) for d in tx_documents]

    try:
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        log.info(f"Upserted {len(ids)} transactions for user {user_id}")
        return len(ids)
    except Exception as e:
        log.error(f"ChromaDB upsert failed for {user_id}: {e}")
        return 0


def query_similar(user_id: str, query_text: str, top_k: int = 5) -> list[dict]:
    """
    Retrieve the most semantically similar transactions to a query.

    Args:
        user_id:    The user identifier.
        query_text: The natural-language query (e.g. "coffee spending last month").
        top_k:      Number of results to return.

    Returns:
        List of dicts with 'text', 'metadata', and 'distance' keys.
    """
    collection = _get_collection(user_id)
    if collection is None:
        return []

    try:
        count = collection.count()
        if count == 0:
            log.debug(f"No transactions indexed for user {user_id}")
            return []

        results = collection.query(
            query_texts=[query_text],
            n_results=min(top_k, count),
        )

        output = []
        docs      = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for doc, meta, dist in zip(docs, metadatas, distances):
            output.append({"text": doc, "metadata": meta, "distance": dist})

        return output
    except Exception as e:
        log.error(f"ChromaDB query failed for {user_id}: {e}")
        return []


def clear_user_store(user_id: str) -> bool:
    """Delete all transaction embeddings for a user (e.g. on account deletion)."""
    client = _get_client()
    if client is None:
        return False
    collection_name = f"user_{user_id.replace('-', '_')}"
    try:
        client.delete_collection(collection_name)
        _collections.pop(user_id, None)
        log.info(f"Cleared vector store for user {user_id}")
        return True
    except Exception as e:
        log.error(f"Failed to clear store for {user_id}: {e}")
        return False
