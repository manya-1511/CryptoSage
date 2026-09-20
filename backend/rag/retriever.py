"""
rag/retriever.py

Phase 7 -- Two-stage retrieval from the ChromaDB knowledge base.

    ChromaDB (candidate_k)  ->  lightweight deterministic rerank  ->  top_k

Both `RAG_CANDIDATE_K` (stage-1 depth) and `RAG_TOP_K` (final depth
handed to the LLM) are configurable via `config.get_settings()`,
never hardcoded.

SIMILARITY SCORE HANDLING
--------------------------
The knowledge-base collection is created (see `rag/ingest.py`) with an
explicit `hnsw:space="cosine"` so ChromaDB's `distances` are always
*cosine distance* (`1 - cosine_similarity`, range ~0-2, 0 = identical)
for both the BGE and TF-IDF backends -- ingestion and retrieval agree
on what "distance" means, rather than retrieval silently assuming a
metric ingestion never configured. `1.0 - distance` is therefore a
mathematically meaningful cosine-similarity approximation, not an
arbitrary transform -- but only because the collection is cosine, and
only approximate when the vectors aren't perfectly unit-normalized (as
BGE's `normalize_embeddings=True` output is, but TF-IDF's raw
`TfidfVectorizer` output is not, so cosine distance there is still a
correct cosine measure even though TF-IDF isn't the same *kind* of
signal semantically -- see `rag/embeddings.py`). Both raw `distance`
and derived `similarity` are returned on every retrieved chunk so a
caller is never handed a lone transformed number without the value it
was computed from.
"""

from __future__ import annotations

import logging
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from config import get_settings
from rag.embeddings import EmbeddingBackend, apply_query_instruction, get_embedding_backend

logger = logging.getLogger("cryptosage.rag.retriever")

settings = get_settings()

# ChromaDB distance metric used for the knowledge-base collection.
# Must match what rag/ingest.py passes to `create_collection(metadata=...)`.
CHROMA_DISTANCE_METRIC = "cosine"


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
    """Build a natural-language retrieval query from the structured pipeline context."""
    parts = [f"{algorithm} {algorithm_family} cryptographic algorithm security"]
    if risk_factors:
        parts.append("risk factors: " + ", ".join(risk_factors))
    if recommendations:
        parts.append("recommendations: " + " ".join(recommendations))
    query = ". ".join(parts)
    logger.debug("Built retrieval query: %s", query)
    return query


# ============================================================
# STAGE 2 -- LIGHTWEIGHT DETERMINISTIC RERANKING
# ============================================================
#
# Deliberately NOT a cross-encoder or any learned reranking model --
# the spec is explicit that the i5/CPU-only target machine must not
# carry that cost. This is pure arithmetic over the chunk's already
# available text/metadata plus the pipeline's already-decided
# algorithm/risk-factor/recommendation context, so it can only ever
# re-order candidates that ChromaDB already retrieved -- it never
# invents or injects new information into a chunk.

def _keyword_match_score(text: str, keywords: list[str]) -> float:
    """Fraction of `keywords` that appear (case-insensitive, substring) in `text`."""
    if not keywords:
        return 0.0
    text_lower = text.lower()
    hits = sum(1 for kw in keywords if kw and kw.lower() in text_lower)
    return hits / len(keywords)


def rerank(
    candidates: list[dict[str, Any]],
    algorithm: str = "",
    algorithm_family: str = "",
    risk_factors: Optional[list[str]] = None,
    recommendations: Optional[list[str]] = None,
    top_k: Optional[int] = None,
    weights: Optional[dict[str, float]] = None,
) -> list[dict[str, Any]]:
    """Rerank ChromaDB's stage-1 `candidates` with a deterministic blended score.

        final_score = w_sem  * semantic_similarity
                    + w_algo * algorithm_match
                    + w_risk * risk_factor_match
                    + w_meta * source_metadata_match

    Every term is computed directly from data already present on the
    candidate (`similarity`, `content`, `metadata`) or already-decided
    upstream context (`algorithm`, `risk_factors`, `recommendations`)
    -- nothing about a chunk's relevance is invented. Returns the
    reordered list truncated to `top_k`, each item annotated with
    `rerank_score` (and the score's components, for debugging/audit).
    """
    if not candidates:
        return []

    risk_factors = risk_factors or []
    recommendations = recommendations or []
    top_k = top_k or settings.RAG_TOP_K
    weights = weights or {
        "semantic": settings.RAG_RERANK_WEIGHT_SEMANTIC,
        "algorithm": settings.RAG_RERANK_WEIGHT_ALGORITHM,
        "risk_factor": settings.RAG_RERANK_WEIGHT_RISK_FACTOR,
        "metadata": settings.RAG_RERANK_WEIGHT_METADATA,
    }

    algorithm_keywords = [kw for kw in (algorithm, algorithm_family) if kw]
    recommendation_keywords = list(recommendations)

    scored: list[dict[str, Any]] = []
    for candidate in candidates:
        content = candidate.get("content", "") or ""
        metadata = candidate.get("metadata", {}) or {}
        semantic_similarity = float(candidate.get("similarity", 0.0) or 0.0)

        algorithm_match = _keyword_match_score(content, algorithm_keywords)
        # Also credit an exact hit on the metadata identifier/title (e.g.
        # a chunk literally titled "AES" for an AES-classified firmware).
        algorithm_match = max(
            algorithm_match,
            _keyword_match_score(f"{metadata.get('title', '')} {metadata.get('identifier', '')}", algorithm_keywords),
        )

        risk_factor_match = _keyword_match_score(content, risk_factors)
        source_metadata_match = _keyword_match_score(content, recommendation_keywords)

        final_score = (
            weights["semantic"] * semantic_similarity
            + weights["algorithm"] * algorithm_match
            + weights["risk_factor"] * risk_factor_match
            + weights["metadata"] * source_metadata_match
        )

        annotated = dict(candidate)
        annotated["rerank_score"] = round(final_score, 4)
        annotated["rerank_components"] = {
            "semantic_similarity": round(semantic_similarity, 4),
            "algorithm_match": round(algorithm_match, 4),
            "risk_factor_match": round(risk_factor_match, 4),
            "source_metadata_match": round(source_metadata_match, 4),
        }
        scored.append(annotated)

    # Stable sort: ties keep ChromaDB's original (semantic) ordering.
    scored.sort(key=lambda item: item["rerank_score"], reverse=True)
    return scored[:top_k]


def retrieve(
    query: str,
    top_k: Optional[int] = None,
    candidate_k: Optional[int] = None,
    persist_dir: Optional[Path] = None,
    algorithm: str = "",
    algorithm_family: str = "",
    risk_factors: Optional[list[str]] = None,
    recommendations: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    """Two-stage retrieval: ChromaDB top-`candidate_k` -> rerank -> top-`top_k`.

    Never raises for an empty result (returns `[]`, logged as a
    warning) -- an empty knowledge base or a query that happens to
    match nothing is a valid, recoverable outcome, not a fatal error.

    Raises:
        RetrieverError: if the knowledge base collection itself can't
            be opened (e.g. never ingested) or the query fails.
    """
    top_k = top_k or settings.RAG_TOP_K
    candidate_k = candidate_k or settings.RAG_CANDIDATE_K
    candidate_k = max(candidate_k, top_k)  # candidate pool must be >= final depth

    embedding_backend = _get_embedding_backend_cached()
    collection = get_collection(persist_dir, embedding_backend)

    query_text = apply_query_instruction(query, embedding_backend)

    logger.info(
        "Document retrieval started: candidate_k=%d, top_k=%d, query=%r",
        candidate_k, top_k, query,
    )
    start = time.perf_counter()
    try:
        results = collection.query(query_texts=[query_text], n_results=candidate_k)
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

    candidates = [
        {
            "content": document,
            "metadata": metadata,
            # `distance` is the raw ChromaDB value (cosine distance --
            # see CHROMA_DISTANCE_METRIC); `similarity` is the derived
            # `1 - distance` approximation. Both are kept so a caller
            # never has to guess how `similarity` was computed.
            "distance": round(float(distance), 4),
            "similarity": round(max(0.0, 1.0 - float(distance)), 4),
        }
        for document, metadata, distance in zip(documents, metadatas, distances)
    ]
    logger.info("Initial retrieval: %d chunk(s).", len(candidates))

    reranked = rerank(
        candidates,
        algorithm=algorithm,
        algorithm_family=algorithm_family,
        risk_factors=risk_factors,
        recommendations=recommendations,
        top_k=top_k,
    )
    retrieval_time_ms = round((time.perf_counter() - start) * 1000, 2)
    logger.info(
        "Reranking: %d -> %d chunks (retrieval_time_ms=%.2f)",
        len(candidates), len(reranked), retrieval_time_ms,
    )
    return reranked
