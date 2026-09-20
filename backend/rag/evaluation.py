"""
rag/evaluation.py

Evaluation module for CryptoSage RAG.

Metrics (original):
    1. Precision@K
    2. Recall@K
    3. Groundedness (lexical)
    4. Citation Correctness (loose substring match)
    5. Expert Evaluation

Metrics (Phase 7 upgrade, additive -- none of the above removed/changed):
    6. Semantic groundedness (embedding-based, optional)
    7. Citation completeness -- do factual-looking claims carry a citation?
    8. Citation validity -- strict match against rag.citations' actual
       valid-label logic (same rule the LLM-output validator uses),
       not the looser identifier-in-content substring match citation_correctness uses
    9. Retrieval / LLM-generation / total latency reporting, sourced
       from an already-measured pipeline run (never estimated here)

The module can be used independently or integrated with the existing
CryptoSage RAG pipeline.

-----------------------------------------------------------------------
FIX (kept from prior revision): `retrieved_documents` must serve two
incompatible roles at once -- document *identity* (needed by
Precision@K / Recall@K, which mirror `metadata["identifier"]` in
citations.py/retriever.py) and document *content* (needed by
Groundedness, which does lexical overlap against the retrieved text).
`retrieved_documents` accepts either:
  - a list of plain strings (legacy behavior, id == content), or
  - a list of dicts shaped like `rag.retriever.retrieve()`'s output,
    e.g. {"content": "...", "metadata": {"identifier": "NIST_AES"}}
    or the simpler {"id": "NIST_AES", "content": "..."}.
Identity-based metrics use the id; content-based metrics use the text.
-----------------------------------------------------------------------
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

Document = Union[str, Dict[str, Any]]


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class RAGEvaluationResult:
    precision_at_k: float
    recall_at_k: float
    groundedness: float
    citation_correctness: float
    expert_score: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "precision_at_k": round(self.precision_at_k, 4),
            "recall_at_k": round(self.recall_at_k, 4),
            "groundedness": round(self.groundedness, 4),
            "citation_correctness": round(self.citation_correctness, 4),
            "expert_score": (
                round(self.expert_score, 4)
                if self.expert_score is not None
                else None
            ),
        }


# ============================================================
# DOCUMENT NORMALIZATION (identity vs. content)
# ============================================================

def _doc_id(doc: Document) -> str:
    """Extract a document's identity (for Precision@K / Recall@K / citation matching)."""
    if isinstance(doc, str):
        return doc
    if "id" in doc:
        return str(doc["id"])
    if "identifier" in doc:
        return str(doc["identifier"])
    metadata = doc.get("metadata", {}) or {}
    if metadata.get("identifier"):
        return str(metadata["identifier"])
    if metadata.get("title"):
        return str(metadata["title"])
    return str(doc.get("content", doc))


def _doc_text(doc: Document) -> str:
    """Extract a document's full text (for Groundedness)."""
    if isinstance(doc, str):
        return doc
    return str(doc.get("content", doc.get("id", "")))


def _doc_match_text(doc: Document) -> str:
    """Text used for citation-correctness substring matching: id + content."""
    if isinstance(doc, str):
        return doc
    return f"{_doc_id(doc)} {_doc_text(doc)}"


def _to_retriever_shaped_docs(retrieved_documents: List[Document]) -> List[Dict[str, Any]]:
    """Normalize a possibly-legacy `retrieved_documents` list into the
    `{"content": ..., "metadata": {...}}` shape `rag.citations` expects,
    so citation_completeness/citation_validity can reuse the exact same
    valid-label logic the LLM-output validator uses rather than
    reimplementing it with different (and possibly diverging) rules.
    """
    shaped = []
    for doc in retrieved_documents:
        if isinstance(doc, dict) and "metadata" in doc:
            shaped.append(doc)
        elif isinstance(doc, dict):
            shaped.append({"content": doc.get("content", ""), "metadata": {"identifier": _doc_id(doc)}})
        else:
            shaped.append({"content": str(doc), "metadata": {"identifier": str(doc)}})
    return shaped


# ============================================================
# TEXT NORMALIZATION
# ============================================================

STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "of", "in", "on", "at", "to", "for", "and", "or", "but", "as", "by",
    "with", "that", "this", "these", "those", "it", "its", "from",
})


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def tokenize(text: str) -> set[str]:
    return set(normalize_text(text).split())


def tokenize_content(text: str) -> set[str]:
    return tokenize(text) - STOPWORDS


# ============================================================
# PRECISION@K
# ============================================================

def precision_at_k(retrieved_documents: List[Document], relevant_documents: List[str], k: int = 5) -> float:
    """Precision@K over the top-K retrieved *chunks*.

    NOTE: unlike recall_at_k, this intentionally does NOT dedupe by
    document identity -- precision asks "of the K chunks I actually
    handed the LLM, how many came from a relevant source", so a
    knowledge base returning several chunks from the same relevant
    document is correctly counted several times (each chunk really did
    occupy a slot in the LLM's limited context). See recall_at_k's
    docstring for why recall needs the opposite (dedup'd) treatment.
    """
    if k <= 0:
        raise ValueError("k must be greater than 0")
    retrieved = retrieved_documents[:k]
    if not retrieved:
        return 0.0
    relevant_set = {normalize_text(doc) for doc in relevant_documents}
    relevant_count = sum(1 for doc in retrieved if normalize_text(_doc_id(doc)) in relevant_set)
    return relevant_count / len(retrieved)


# ============================================================
# RECALL@K
# ============================================================

def recall_at_k(retrieved_documents: List[Document], relevant_documents: List[str], k: int = 5) -> float:
    """Recall@K = (unique relevant *documents* covered by the top-K
    chunks) / (total relevant documents).

    Deliberately deduped by document identity (unlike precision_at_k):
    recall asks "of the documents I needed, how many did I surface at
    all", so once the knowledge base is chunked -- meaning several of
    the top-K entries can be different chunks of the *same* relevant
    document -- counting every chunk hit instead of every unique
    document hit would let recall exceed 1.0 (e.g. 3 chunks from 1
    relevant document but only 1 relevant document total). A bare
    per-chunk count is only correct when retrieved_documents are
    already one-row-per-document, which chunked retrieval never
    guarantees.
    """
    if k <= 0:
        raise ValueError("k must be greater than 0")
    if not relevant_documents:
        return 0.0
    retrieved = retrieved_documents[:k]
    relevant_set = {normalize_text(doc) for doc in relevant_documents}
    retrieved_relevant_docs = {normalize_text(_doc_id(doc)) for doc in retrieved} & relevant_set
    return len(retrieved_relevant_docs) / len(relevant_set)


# ============================================================
# LIGHTWEIGHT TEXTUAL SUPPORT
# ============================================================

def calculate_text_support(statement: str, context: str) -> float:
    statement_tokens = tokenize_content(statement)
    context_tokens = tokenize(context)
    if not statement_tokens or not context_tokens:
        return 0.0
    overlap = statement_tokens.intersection(context_tokens)
    return len(overlap) / len(statement_tokens)


# ============================================================
# GROUNDEDNESS (lexical)
# ============================================================

def groundedness(answer: str, retrieved_context: List[Document], threshold: float = 0.50) -> float:
    if not answer or not retrieved_context:
        return 0.0
    context = " ".join(_doc_text(doc) for doc in retrieved_context)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", answer.strip()) if s.strip()]
    if not sentences:
        return 0.0
    supported = sum(1 for s in sentences if calculate_text_support(s, context) >= threshold)
    return supported / len(sentences)


# ============================================================
# SEMANTIC GROUNDEDNESS (optional, embedding-based)
# ============================================================

def semantic_groundedness(
    answer: str,
    retrieved_context: List[Document],
    threshold: float = 0.60,
    embedding_backend: Any = None,
) -> Optional[float]:
    if not answer or not retrieved_context:
        return None

    if embedding_backend is None:
        try:
            from rag.retriever import _get_embedding_backend_cached

            embedding_backend = _get_embedding_backend_cached()
        except Exception:  # noqa: BLE001 - optional metric, never raises
            return None

    if getattr(embedding_backend, "is_fallback", True):
        return None

    try:
        import numpy as np
    except ImportError:
        return None

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", answer.strip()) if s.strip()]
    context_texts = [_doc_text(doc) for doc in retrieved_context if _doc_text(doc)]
    if not sentences or not context_texts:
        return None

    try:
        sentence_vectors = np.array(embedding_backend.embed(sentences))
        context_vectors = np.array(embedding_backend.embed(context_texts))
    except Exception:  # noqa: BLE001
        return None

    def _cosine_sim_matrix(a: "np.ndarray", b: "np.ndarray") -> "np.ndarray":
        a_norm = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-12)
        b_norm = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-12)
        return a_norm @ b_norm.T

    similarities = _cosine_sim_matrix(sentence_vectors, context_vectors)
    max_similarity_per_sentence = similarities.max(axis=1)
    supported = int((max_similarity_per_sentence >= threshold).sum())
    return supported / len(sentences)


# ============================================================
# CITATION EXTRACTION
# ============================================================

def extract_citations(answer: str) -> List[str]:
    if not answer:
        return []
    citations = re.findall(r"\[([^\]]+)\]", answer)
    return list(dict.fromkeys(citations))


# ============================================================
# CITATION CORRECTNESS (loose -- original behavior, unchanged)
# ============================================================

def citation_correctness(answer: str, retrieved_documents: List[Document]) -> float:
    citations = extract_citations(answer)
    if not citations:
        return 0.0

    normalized_documents = [normalize_text(_doc_match_text(doc)) for doc in retrieved_documents]
    correct = 0
    for citation in citations:
        citation_normalized = normalize_text(citation)
        for document in normalized_documents:
            if citation_normalized in document or document in citation_normalized:
                correct += 1
                break
    return correct / len(citations)


# ============================================================
# CITATION VALIDITY (strict -- Phase 7 upgrade)
# ============================================================

def citation_validity(answer: str, retrieved_documents: List[Document]) -> float:
    """Fraction of `[LABEL]` markers in `answer` that exactly match a
    citation label actually derivable from `retrieved_documents` (via
    `rag.citations.valid_citation_labels` -- the same rule
    `rag/validation.py` uses to gate the LLM/template fallback).

    Stricter than `citation_correctness` (which allows any substring
    match against raw id+content), so a study reporting both can show
    how much of the loose metric's "correctness" survives strict label
    matching -- useful for the IEEE-style writeup's honesty about what
    each metric actually measures.
    """
    from rag.citations import extract_citation_markers, format_citation, valid_citation_labels

    citations = [format_citation(doc.get("metadata", {})) for doc in _to_retriever_shaped_docs(retrieved_documents)]
    allowed = valid_citation_labels(citations)
    markers = extract_citation_markers(answer)
    if not markers:
        return 0.0
    correct = sum(1 for m in markers if m.strip().lower() in allowed)
    return correct / len(markers)


# ============================================================
# CITATION COMPLETENESS (Phase 7 upgrade)
# ============================================================

_FACTUAL_HEDGE_RE = re.compile(r"does not establish this claim", re.IGNORECASE)


def citation_completeness(answer: str) -> float:
    """Fraction of sentences that look like they're making a factual
    claim (i.e. are not the deterministic "the retrieved evidence does
    not establish this claim" disclaimer, and are not trivially short
    boilerplate) that carry at least one `[LABEL]` citation.

    This measures *coverage*, not correctness -- a wrong-but-cited
    sentence still counts as complete here; pair with
    `citation_validity`/`citation_correctness` for correctness.
    """
    if not answer:
        return 0.0

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", answer.strip()) if s.strip()]
    factual_sentences = [
        s for s in sentences
        if len(s.split()) >= 6 and not _FACTUAL_HEDGE_RE.search(s)
    ]
    if not factual_sentences:
        return 1.0  # nothing required a citation, so coverage is vacuously complete

    cited = sum(1 for s in factual_sentences if re.search(r"\[([^\[\]]+)\]", s))
    return cited / len(factual_sentences)


# ============================================================
# EXPERT EVALUATION
# ============================================================

def expert_evaluation(relevance: float, correctness: float, completeness: float, citation_quality: float) -> float:
    scores = [relevance, correctness, completeness, citation_quality]
    for score in scores:
        if not 1 <= score <= 5:
            raise ValueError("Expert scores must be between 1 and 5.")
    return sum(scores) / len(scores)


# ============================================================
# COMPLETE SINGLE-QUERY EVALUATION
# ============================================================

def evaluate_query(
    question: str,
    answer: str,
    retrieved_documents: List[Document],
    relevant_documents: Optional[List[str]],
    k: int = 5,
    expert_scores: Optional[Dict[str, float]] = None,
    compute_semantic_groundedness: bool = False,
    latencies_ms: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Evaluate one RAG query.

    `latencies_ms`: optional `{"retrieval_time_ms": ..., "llm_generation_time_ms": ...,
    "total_generation_time_ms": ...}` as already measured by
    `rag.explain.explain_firmware()` -- reported here verbatim, never
    estimated or fabricated. Omit (or leave a key out) when not
    available; missing latency keys are reported as `None`.
    """
    has_ground_truth = bool(relevant_documents)

    precision = precision_at_k(retrieved_documents, relevant_documents, k) if has_ground_truth else None
    recall = recall_at_k(retrieved_documents, relevant_documents, k) if has_ground_truth else None
    ground = groundedness(answer, retrieved_documents)
    semantic_ground = semantic_groundedness(answer, retrieved_documents) if compute_semantic_groundedness else None
    citation = citation_correctness(answer, retrieved_documents)
    validity = citation_validity(answer, retrieved_documents)
    completeness = citation_completeness(answer)

    expert_score = None
    if expert_scores:
        expert_score = expert_evaluation(
            relevance=expert_scores["relevance"],
            correctness=expert_scores["correctness"],
            completeness=expert_scores["completeness"],
            citation_quality=expert_scores["citation_quality"],
        )

    latencies_ms = latencies_ms or {}

    metrics: Dict[str, Any] = {
        "precision_at_k": round(precision, 4) if precision is not None else None,
        "recall_at_k": round(recall, 4) if recall is not None else None,
        "groundedness": round(ground, 4),
        "semantic_groundedness": round(semantic_ground, 4) if semantic_ground is not None else None,
        "citation_correctness": round(citation, 4),
        "citation_validity": round(validity, 4),
        "citation_completeness": round(completeness, 4),
        "expert_score": round(expert_score, 4) if expert_score is not None else None,
        "ground_truth_available": has_ground_truth,
        "retrieval_time_ms": latencies_ms.get("retrieval_time_ms"),
        "llm_generation_time_ms": latencies_ms.get("llm_generation_time_ms"),
        "total_generation_time_ms": latencies_ms.get("total_generation_time_ms"),
    }

    return {
        "question": question,
        "answer": answer,
        "retrieved_documents": retrieved_documents,
        "relevant_documents": relevant_documents,
        "metrics": metrics,
    }


# ============================================================
# DATASET-LEVEL EVALUATION
# ============================================================

def evaluate_dataset(
    evaluation_dataset: List[Dict[str, Any]],
    k: int = 5,
    compute_semantic_groundedness: bool = False,
) -> Dict[str, Any]:
    """Evaluate multiple RAG questions.

    Expected dataset format:

    [
        {
            "question": "...",
            "answer": "...",
            "retrieved_documents": [...],
            "relevant_documents": [...],   # omit or [] if ground truth is missing
            "expert_scores": {"relevance": 5, "correctness": 4, "completeness": 4, "citation_quality": 5},
            "latencies_ms": {"retrieval_time_ms": ..., "llm_generation_time_ms": ..., "total_generation_time_ms": ...},
        }
    ]

    Aggregate Precision@K/Recall@K are computed only over items that
    actually have ground truth. If NO item has ground truth, the
    aggregate is `None` with `precision_recall_coverage: 0` rather than
    fabricated as 0.0.
    """
    if not evaluation_dataset:
        raise ValueError("Evaluation dataset cannot be empty.")

    results = []
    for item in evaluation_dataset:
        result = evaluate_query(
            question=item["question"],
            answer=item["answer"],
            retrieved_documents=item["retrieved_documents"],
            relevant_documents=item.get("relevant_documents"),
            k=k,
            expert_scores=item.get("expert_scores"),
            compute_semantic_groundedness=compute_semantic_groundedness,
            latencies_ms=item.get("latencies_ms"),
        )
        results.append(result)

    precision_scores = [r["metrics"]["precision_at_k"] for r in results if r["metrics"]["precision_at_k"] is not None]
    recall_scores = [r["metrics"]["recall_at_k"] for r in results if r["metrics"]["recall_at_k"] is not None]
    groundedness_scores = [r["metrics"]["groundedness"] for r in results]
    semantic_groundedness_scores = [
        r["metrics"]["semantic_groundedness"] for r in results if r["metrics"]["semantic_groundedness"] is not None
    ]
    citation_scores = [r["metrics"]["citation_correctness"] for r in results]
    citation_validity_scores = [r["metrics"]["citation_validity"] for r in results]
    citation_completeness_scores = [r["metrics"]["citation_completeness"] for r in results]
    expert_scores = [r["metrics"]["expert_score"] for r in results if r["metrics"]["expert_score"] is not None]
    retrieval_latencies = [r["metrics"]["retrieval_time_ms"] for r in results if r["metrics"]["retrieval_time_ms"] is not None]
    llm_latencies = [r["metrics"]["llm_generation_time_ms"] for r in results if r["metrics"]["llm_generation_time_ms"] is not None]
    total_latencies = [r["metrics"]["total_generation_time_ms"] for r in results if r["metrics"]["total_generation_time_ms"] is not None]

    def _avg(values: List[float]) -> Optional[float]:
        return round(sum(values) / len(values), 4) if values else None

    summary = {
        f"precision@{k}": _avg(precision_scores),
        f"recall@{k}": _avg(recall_scores),
        "precision_recall_coverage": len(precision_scores),
        "groundedness": round(sum(groundedness_scores) / len(groundedness_scores), 4),
        "semantic_groundedness": _avg(semantic_groundedness_scores),
        "citation_correctness": round(sum(citation_scores) / len(citation_scores), 4),
        "citation_validity": round(sum(citation_validity_scores) / len(citation_validity_scores), 4),
        "citation_completeness": round(sum(citation_completeness_scores) / len(citation_completeness_scores), 4),
        "expert_evaluation": _avg(expert_scores),
        "avg_retrieval_time_ms": _avg(retrieval_latencies),
        "avg_llm_generation_time_ms": _avg(llm_latencies),
        "avg_total_generation_time_ms": _avg(total_latencies),
        "number_of_queries": len(results),
    }

    return {"summary": summary, "results": results}


# ============================================================
# SIMPLE TEST
# ============================================================

if __name__ == "__main__":
    evaluation_data = [
        {
            "question": "What is AES?",
            "answer": "AES is a symmetric block cipher used for secure encryption [NIST_AES].",
            "retrieved_documents": [
                {"id": "NIST_AES", "content": "NIST FIPS 197 specifies the Advanced Encryption Standard (AES), a symmetric block cipher used for secure encryption of electronic data."},
                {"id": "CWE_327", "content": "CWE-327 describes the use of a broken or risky cryptographic algorithm as a common software weakness."},
                {"id": "crypto_algorithms", "content": "An overview of common cryptographic algorithms, including AES, RSA, and SHA-256."},
                {"id": "key_management", "content": "Key management best practices cover generation, distribution, storage, and rotation of cryptographic keys."},
                {"id": "AES_security", "content": "AES security analysis shows it remains secure against all known practical cryptanalytic attacks when used with a sufficient key length."},
            ],
            "relevant_documents": ["NIST_AES", "AES_security"],
            "expert_scores": {"relevance": 5, "correctness": 5, "completeness": 4, "citation_quality": 5},
        }
    ]

    results = evaluate_dataset(evaluation_data, k=5)

    print("\n========================================")
    print("CryptoSage RAG Evaluation")
    print("========================================")
    print("\nSummary:")
    for metric, value in results["summary"].items():
        print(f"{metric}: {value}")
    print("\n========================================")
