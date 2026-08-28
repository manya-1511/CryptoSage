"""
rag/retriever.py

Phase 7 -- Top-K document retrieval from the ChromaDB knowledge base.

Given the structured outputs of earlier phases (feature vector, ML
prediction, risk score, recommendations), builds a natural-language
retrieval query and returns the most relevant supporting knowledge-base
chunks. Retrieval depth (`top_k`) is configurable
(`settings.RAG_TOP_K`), never hardcoded.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from config import get_settings
from rag.embeddings import EmbeddingBackend, apply_query_instruction, get_embedding_backend

logger = logging.getLogger("cryptosage.rag.retriever")

settings = get_settings()


class RetrieverError(RuntimeError):
    """Raised when the knowledge base collection can't be loaded or queried."""


@lru_cache(maxsize=1)
def _get_embedding_backend_cached() -> EmbeddingBackend:
    """Load the embedding backend once per process and reuse it."""
    return get_embedding_backend(settings.RAG_EMBEDDING_MODEL)


def get_collection(persist_dir: Optional[Path] = None, embedding_backend: Optional[EmbeddingBackend] = None):
    """Open the persisted ChromaDB knowledge-base collection.

    Raises:
        RetrieverError: if the collection doesn't exist yet (the
            knowledge base hasn't been ingested -- run
            `rag.ingest.ingest_knowledge_base()` first) or can't be
            opened for any other reason.
    """
    import chromadb

    persist_dir = persist_dir or settings.RAG_CHROMA_PERSIST_DIR
    embedding_backend = embedding_backend or _get_embedding_backend_cached()

    if not persist_dir.exists():
        message = (
            f"Knowledge base is not ingested yet (no ChromaDB store at {persist_dir}). "
            "Run rag.ingest.ingest_knowledge_base() first."
        )
        logger.error(message)
        raise RetrieverError(message)

    try:
        client = chromadb.PersistentClient(path=str(persist_dir))
        return client.get_collection(name=settings.RAG_COLLECTION_NAME, embedding_function=embedding_backend.embed)
    except Exception as exc:  # noqa: BLE001
        message = f"Could not open knowledge base collection '{settings.RAG_COLLECTION_NAME}': {exc}"
        logger.error(message)
        raise RetrieverError(message) from exc


def build_retrieval_query(
    algorithm: str,
    algorithm_family: str,
    risk_factors: list[str],
    recommendations: list[str],
) -> str:
    """Build a natural-language retrieval query from the structured pipeline context.

    Combines the identified algorithm/family with the names of every
    triggered risk factor and recommendation topic, so retrieval
    surfaces documents relevant to *why* this specific firmware scored
    the way it did -- not just generic documents about the algorithm.
    """
    parts = [f"{algorithm} {algorithm_family} cryptographic algorithm security"]
    if risk_factors:
        parts.append("risk factors: " + ", ".join(risk_factors))
    if recommendations:
        parts.append("recommendations: " + " ".join(recommendations))
    query = ". ".join(parts)
    logger.debug("Built retrieval query: %s", query)
    return query


def retrieve(
    query: str,
    top_k: Optional[int] = None,
    persist_dir: Optional[Path] = None,
) -> list[dict[str, Any]]:
    """Retrieve the top-K most relevant knowledge-base chunks for `query`.

    Never raises for an empty result (returns `[]`, logged as a
    warning) -- an empty knowledge base or a query that happens to
    match nothing is a valid, recoverable outcome, not a fatal error.

    Raises:
        RetrieverError: if the knowledge base collection itself can't
            be opened (e.g. never ingested).
    """
    top_k = top_k or settings.RAG_TOP_K
    embedding_backend = _get_embedding_backend_cached()
    collection = get_collection(persist_dir, embedding_backend)

    query_text = apply_query_instruction(query, embedding_backend)

    logger.info("Document retrieval started: top_k=%d, query=%r", top_k, query)
    try:
        results = collection.query(query_texts=[query_text], n_results=top_k)
    except Exception as exc:  # noqa: BLE001
        message = f"Retrieval query failed: {exc}"
        logger.error(message)
        raise RetrieverError(message) from exc

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    if not documents:
        logger.warning("Retrieval returned no results for query: %r", query)
        return []

    retrieved = [
        {
            "content": document,
            "metadata": metadata,
            # ChromaDB returns a distance (lower = more similar); expose
            # a similarity score in [0, 1] (approximately) for readability.
            "similarity": round(max(0.0, 1.0 - distance), 4),
        }
        for document, metadata, distance in zip(documents, metadatas, distances)
    ]
    logger.info("Document retrieval completed: %d chunk(s) retrieved.", len(retrieved))
    return retrieved
