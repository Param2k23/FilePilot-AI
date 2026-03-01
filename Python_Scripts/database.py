"""
database.py — ChromaDB vector store for FilePilot AI

Stores file move records and enables semantic search by intent,
e.g. "where is my visa document?" finds passport_scan.pdf.

Database is stored in ~/.cleanslate/chroma/ so it is portable
and independent of the project directory.
"""

from __future__ import annotations

import os
from pathlib import Path

import chromadb
from chromadb.config import Settings

from models import FileRecord

# ── Storage path ──────────────────────────────────────────────────────────────
_DB_DIR = Path.home() / ".cleanslate" / "chroma"
_COLLECTION_NAME = "file_moves"


def _get_client() -> chromadb.ClientAPI:
    """Return a persistent ChromaDB client stored in ~/.cleanslate/chroma/."""
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=str(_DB_DIR),
        settings=Settings(anonymized_telemetry=False),
    )


def init_db() -> chromadb.Collection:
    """
    Initialize (or open) the ChromaDB collection.

    Returns:
        The 'file_moves' collection ready for reads/writes.
    """
    client = _get_client()
    collection = client.get_or_create_collection(
        name=_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    return collection


def store_move(record: FileRecord) -> None:
    """
    Embed and persist a FileRecord in ChromaDB.

    The document text combines filename + reason so semantic queries
    like "budget spreadsheet" or "visa document" can retrieve it.

    Args:
        record: A validated FileRecord to store.
    """
    collection = init_db()

    document = f"{record.filename} — {record.reason}"
    metadata = {
        "filename": record.filename,
        "extension": record.extension,
        "original_path": record.original_path,
        "new_path": record.new_path,
        "reason": record.reason,
        "timestamp": record.timestamp,
    }

    collection.upsert(
        ids=[record.id],
        documents=[document],
        metadatas=[metadata],
    )


def search_files(query: str, n_results: int = 5) -> list[dict]:
    """
    Semantic search over stored file records.

    Args:
        query: Natural language query, e.g. "where is my tax form?".
        n_results: Maximum number of results to return.

    Returns:
        List of metadata dicts, each containing filename, original_path,
        new_path, reason, and timestamp.
    """
    collection = init_db()

    count = collection.count()
    if count == 0:
        return []

    actual_n = min(n_results, count)

    results = collection.query(
        query_texts=[query],
        n_results=actual_n,
        include=["metadatas", "distances"],
    )

    records: list[dict] = []
    for meta, dist in zip(
        results["metadatas"][0],
        results["distances"][0],
    ):
        records.append({**meta, "relevance_score": round(1 - dist, 4)})

    return records


def list_all_moves() -> list[dict]:
    """Return all stored move records sorted newest-first."""
    collection = init_db()
    if collection.count() == 0:
        return []
    results = collection.get(include=["metadatas"])
    # ChromaDB always returns ids regardless of include list
    records = [
        {**meta, "id": rec_id}
        for meta, rec_id in zip(results["metadatas"], results["ids"])
    ]
    # Sort newest-first by timestamp (ISO string sort works fine)
    records.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    return records


def undo_move(record_id: str) -> bool:
    """
    Remove a move record from ChromaDB by its ID.

    This is the index-side half of an undo; pair with restore_file()
    in organizer.py to also move the file back on disk.

    Args:
        record_id: The UUID string stored as the ChromaDB document ID.

    Returns:
        True if the record was found and deleted, False otherwise.
    """
    collection = init_db()
    try:
        collection.delete(ids=[record_id])
        return True
    except Exception:
        return False
