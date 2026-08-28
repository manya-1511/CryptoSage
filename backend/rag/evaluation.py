"""
rag/evaluation.py

Evaluation module for CryptoSage RAG.

Metrics:
    1. Precision@K
    2. Recall@K
    3. Groundedness
    4. Citation Correctness
    5. Expert Evaluation

The module can be used independently or integrated with the existing
CryptoSage RAG pipeline.

-----------------------------------------------------------------------
FIX (see module history): `retrieved_documents` previously had to serve
two incompatible roles at once -- document *identity* (needed by
Precision@K / Recall@K, which mirror `metadata["identifier"]` in
citations.py/retriever.py) and document *content* (needed by
Groundedness, which does lexical overlap against the retrieved text).
Passing bare identifiers (e.g. "NIST_AES") satisfied the identity-based
metrics but starved Groundedness of any real text to match against,
silently producing a groundedness of 0.0 regardless of answer quality.

`retrieved_documents` now accepts either:
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
    """Extract a document's identity (for Precision@K / Recall@K / citation matching).

    Plain strings are their own id (legacy behavior). Dicts prefer an
    explicit "id"/"identifier", then `metadata.identifier`, then
    `metadata.title`, falling back to the content itself so a
    malformed dict never crashes evaluation.
    """
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
    """Extract a document's full text (for Groundedness).

    Plain strings are their own text (legacy behavior). Dicts use
    "content" when present.
    """
    if isinstance(doc, str):
        return doc
    return str(doc.get("content", doc.get("id", "")))


def _doc_match_text(doc: Document) -> str:
    """Text used for citation-correctness substring matching: id + content,
    so a citation like [NIST_AES] matches whether the identifier or the
    passage text (or both) carries it.
    """
    if isinstance(doc, str):
        return doc
    return f"{_doc_id(doc)} {_doc_text(doc)}"


# ============================================================
# TEXT NORMALIZATION
# ============================================================

# Small, generic stopword list. These are excluded from the
# *statement* side of the groundedness lexical-overlap ratio so that
# function words (which will trivially appear in almost any English
# context) don't dilute the signal from actual content words.
STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "of", "in", "on", "at", "to", "for", "and", "or", "but", "as", "by",
    "with", "that", "this", "these", "those", "it", "its", "from",
})


def normalize_text(text: str) -> str:
    """
    Normalize text for lightweight textual comparison.
    """
    if not text:
        return ""

    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def tokenize(text: str) -> set[str]:
    """
    Convert text into a set of normalized tokens.
    """
    return set(normalize_text(text).split())


def tokenize_content(text: str) -> set[str]:
    """Like `tokenize`, but drops common stopwords -- used for the
    statement side of groundedness so the ratio reflects overlap of
    meaningful content words rather than being padded/diluted by
    function words.
    """
    return tokenize(text) - STOPWORDS


# ============================================================
# PRECISION@K
# ============================================================

def precision_at_k(
    retrieved_documents: List[Document],
    relevant_documents: List[str],
    k: int = 5,
) -> float:
    """
    Calculate Precision@K.

    Precision@K =
        relevant retrieved documents / K

    Example:

        Retrieved:
            [A, B, C, D, E]

        Relevant:
            [A, C, F]

        Precision@5 = 2 / 5 = 0.40

    `retrieved_documents` may be plain strings (treated as identifiers)
    or dicts shaped like `retriever.retrieve()`'s output -- identity is
    extracted via `_doc_id`.
    """

    if k <= 0:
        raise ValueError("k must be greater than 0")

    retrieved = retrieved_documents[:k]

    if not retrieved:
        return 0.0

    relevant_set = {
        normalize_text(doc)
        for doc in relevant_documents
    }

    relevant_count = sum(
        1
        for doc in retrieved
        if normalize_text(_doc_id(doc)) in relevant_set
    )

    return relevant_count / len(retrieved)


# ============================================================
# RECALL@K
# ============================================================

def recall_at_k(
    retrieved_documents: List[Document],
    relevant_documents: List[str],
    k: int = 5,
) -> float:
    """
    Calculate Recall@K.

    Recall@K =
        relevant retrieved documents / total relevant documents
    """

    if k <= 0:
        raise ValueError("k must be greater than 0")

    if not relevant_documents:
        return 0.0

    retrieved = retrieved_documents[:k]

    relevant_set = {
        normalize_text(doc)
        for doc in relevant_documents
    }

    retrieved_relevant = sum(
        1
        for doc in retrieved
        if normalize_text(_doc_id(doc)) in relevant_set
    )

    return retrieved_relevant / len(relevant_set)


# ============================================================
# LIGHTWEIGHT TEXTUAL SUPPORT
# ============================================================

def calculate_text_support(
    statement: str,
    context: str,
) -> float:
    """
    Estimate how strongly a statement is supported by context.

    This is a lightweight lexical groundedness metric: the fraction of
    the statement's *content* words (stopwords excluded) that also
    appear somewhere in the context.

    It does NOT claim semantic/NLI-level understanding -- it will miss
    paraphrases and synonyms (e.g. "secure" vs. "security"). For
    production research evaluation, this can later be replaced or
    supplemented with an embedding-based similarity (CryptoSage's own
    `rag.embeddings` backend) or an LLM/NLI-based evaluator.
    """

    statement_tokens = tokenize_content(statement)
    context_tokens = tokenize(context)

    if not statement_tokens:
        return 0.0

    if not context_tokens:
        return 0.0

    overlap = statement_tokens.intersection(context_tokens)

    return len(overlap) / len(statement_tokens)


# ============================================================
# GROUNDEDNESS
# ============================================================

def groundedness(
    answer: str,
    retrieved_context: List[Document],
    threshold: float = 0.50,
) -> float:
    """
    Calculate LEXICAL groundedness of the generated answer (see the
    `calculate_text_support` docstring -- this is word-overlap, not
    semantic entailment; see `semantic_groundedness()` below for an
    embedding-based complement).

    The answer is divided into sentences. Each sentence is compared
    against the retrieved context.

    Score:
        supported sentences / total sentences

    A sentence is considered grounded when its lexical support
    exceeds the supplied threshold.

    `retrieved_context` must carry actual passage text to be useful --
    plain strings are used as-is, and dicts shaped like
    `retriever.retrieve()`'s output have their "content" field
    extracted via `_doc_text`. Passing bare identifiers here (rather
    than passage content) will under-report groundedness, since there
    is no real text for the answer to be lexically grounded in.
    """

    if not answer:
        return 0.0

    if not retrieved_context:
        return 0.0

    context = " ".join(_doc_text(doc) for doc in retrieved_context)

    sentences = re.split(
        r"(?<=[.!?])\s+",
        answer.strip(),
    )

    sentences = [
        sentence.strip()
        for sentence in sentences
        if sentence.strip()
    ]

    if not sentences:
        return 0.0

    supported = 0

    for sentence in sentences:
        support = calculate_text_support(
            sentence,
            context,
        )

        if support >= threshold:
            supported += 1

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
    """
    Optional complement to `groundedness()` (lexical overlap): for each
    answer sentence, embed it and every retrieved chunk with
    CryptoSage's own configured embedding backend (rag.embeddings,
    normally BGE) and take the maximum cosine similarity across chunks
    as that sentence's support score. Fraction of sentences whose max
    similarity clears `threshold` is returned.

    This catches paraphrases/synonyms lexical overlap misses (e.g.
    "secure" vs. "security"), at the cost of depending on the
    embedding backend actually being available.

    Returns None (never 0.0, never fabricated) when it cannot be
    computed -- e.g. no embedding backend configured/loadable, or the
    active backend is the TF-IDF fallback where "cosine similarity"
    doesn't carry the same semantic meaning it does for BGE. A None
    result should be reported as "not computed", not silently treated
    as a groundedness of zero.

    This metric is entirely optional/configurable: callers that don't
    pass `embedding_backend` and don't want the dependency on
    rag.embeddings simply never call this function; `groundedness()`
    above is unaffected either way.
    """
    if not answer or not retrieved_context:
        return None

    if embedding_backend is None:
        try:
            from rag.retriever import _get_embedding_backend_cached

            embedding_backend = _get_embedding_backend_cached()
        except Exception:  # noqa: BLE001 - optional metric, never raises
            return None

    if getattr(embedding_backend, "is_fallback", True):
        # TF-IDF cosine similarity is not a semantic signal in the same
        # sense BGE's is; reporting a number here would misrepresent
        # what was actually measured.
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
    except Exception:  # noqa: BLE001 - optional metric, never raises
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
    """
    Extract common citation formats from an answer.

    Supported examples:

        [1]
        [2]
        [3]

        [NIST]
        [CWE]
        [OWASP]

    Returns unique citation identifiers.
    """

    if not answer:
        return []

    citations = re.findall(
        r"\[([^\]]+)\]",
        answer,
    )

    return list(dict.fromkeys(citations))


# ============================================================
# CITATION CORRECTNESS
# ============================================================

def citation_correctness(
    answer: str,
    retrieved_documents: List[Document],
) -> float:
    """
    Estimate citation correctness.

    A citation is considered correct when:

        1. A citation exists in the answer.
        2. The cited identifier can be matched against one of the
           retrieved documents' id and/or content.

    Example:

        Answer:
            "AES is a symmetric encryption algorithm [NIST_AES]."

        Retrieved documents:
            ["NIST_AES", "CWE_327"]

        Citation [NIST_AES] is considered valid.
    """

    citations = extract_citations(answer)

    if not citations:
        return 0.0

    normalized_documents = [
        normalize_text(_doc_match_text(doc))
        for doc in retrieved_documents
    ]

    correct = 0

    for citation in citations:
        citation_normalized = normalize_text(citation)

        for document in normalized_documents:
            if (
                citation_normalized in document
                or document in citation_normalized
            ):
                correct += 1
                break

    return correct / len(citations)


# ============================================================
# EXPERT EVALUATION
# ============================================================

def expert_evaluation(
    relevance: float,
    correctness: float,
    completeness: float,
    citation_quality: float,
) -> float:
    """
    Calculate an overall expert evaluation score.

    Each input should be rated from 1 to 5.

    Criteria:

        relevance       -> Does the answer address the question?
        correctness     -> Is the answer technically correct?
        completeness    -> Does it cover the important information?
        citation_quality -> Are sources/citations appropriate?

    Returns:
        Average score from 1 to 5.
    """

    scores = [
        relevance,
        correctness,
        completeness,
        citation_quality,
    ]

    for score in scores:
        if not 1 <= score <= 5:
            raise ValueError(
                "Expert scores must be between 1 and 5."
            )

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
) -> Dict[str, Any]:
    """
    Evaluate one RAG query.

    Parameters
    ----------
    question:
        User's question.

    answer:
        Generated RAG answer.

    retrieved_documents:
        Documents/chunks retrieved by the retriever. Either plain
        strings (identifiers) or dicts shaped like
        `retriever.retrieve()`'s output (with "content" and/or
        "metadata"/"id"). Groundedness needs real content text to be
        meaningful; Precision@K/Recall@K/citation matching only need
        identity, which is derived automatically either way.

    relevant_documents:
        Ground-truth relevant document identifiers. If None or empty,
        Precision@K/Recall@K are reported as `None` (missing ground
        truth), never silently fabricated as 0.0 -- a 0.0 would be
        indistinguishable from "no relevant documents were retrieved",
        which is a different, false claim.

    k:
        Number of retrieved documents used for Precision@K
        and Recall@K.

    expert_scores:
        Optional dictionary:

        {
            "relevance": 5,
            "correctness": 4,
            "completeness": 4,
            "citation_quality": 5
        }

    compute_semantic_groundedness:
        If True, also computes `semantic_groundedness()` (requires the
        configured embedding backend to be BGE, not the TF-IDF
        fallback -- returns None otherwise, never fabricated).
    """

    has_ground_truth = bool(relevant_documents)

    precision = (
        precision_at_k(retrieved_documents, relevant_documents, k)
        if has_ground_truth else None
    )

    recall = (
        recall_at_k(retrieved_documents, relevant_documents, k)
        if has_ground_truth else None
    )

    ground = groundedness(
        answer,
        retrieved_documents,
    )

    semantic_ground = (
        semantic_groundedness(answer, retrieved_documents)
        if compute_semantic_groundedness else None
    )

    citation = citation_correctness(
        answer,
        retrieved_documents,
    )

    expert_score = None

    if expert_scores:
        expert_score = expert_evaluation(
            relevance=expert_scores["relevance"],
            correctness=expert_scores["correctness"],
            completeness=expert_scores["completeness"],
            citation_quality=expert_scores["citation_quality"],
        )

    metrics: Dict[str, Any] = {
        "precision_at_k": round(precision, 4) if precision is not None else None,
        "recall_at_k": round(recall, 4) if recall is not None else None,
        "groundedness": round(ground, 4),
        "semantic_groundedness": round(semantic_ground, 4) if semantic_ground is not None else None,
        "citation_correctness": round(citation, 4),
        "expert_score": round(expert_score, 4) if expert_score is not None else None,
        "ground_truth_available": has_ground_truth,
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
    """
    Evaluate multiple RAG questions.

    Expected dataset format:

    [
        {
            "question": "...",
            "answer": "...",
            "retrieved_documents": [...],
            "relevant_documents": [...],   # omit or [] if ground truth is missing

            "expert_scores": {
                "relevance": 5,
                "correctness": 4,
                "completeness": 4,
                "citation_quality": 5
            }
        }
    ]

    Aggregate Precision@K/Recall@K are computed only over items that
    actually have ground truth (`relevant_documents` non-empty). If NO
    item in the dataset has ground truth, the aggregate is reported as
    `None` with `precision_recall_coverage: 0` rather than fabricated
    -- callers must not mistake "no ground truth was provided" for "0%
    precision".
    """

    if not evaluation_dataset:
        raise ValueError(
            "Evaluation dataset cannot be empty."
        )

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
        )

        results.append(result)

    # --------------------------------------------------------
    # Aggregate metrics
    # --------------------------------------------------------

    precision_scores = [r["metrics"]["precision_at_k"] for r in results if r["metrics"]["precision_at_k"] is not None]
    recall_scores = [r["metrics"]["recall_at_k"] for r in results if r["metrics"]["recall_at_k"] is not None]

    groundedness_scores = [
        r["metrics"]["groundedness"]
        for r in results
    ]

    semantic_groundedness_scores = [
        r["metrics"]["semantic_groundedness"]
        for r in results
        if r["metrics"]["semantic_groundedness"] is not None
    ]

    citation_scores = [
        r["metrics"]["citation_correctness"]
        for r in results
    ]

    expert_scores = [
        r["metrics"]["expert_score"]
        for r in results
        if r["metrics"]["expert_score"] is not None
    ]

    summary = {
        f"precision@{k}": (
            round(sum(precision_scores) / len(precision_scores), 4)
            if precision_scores else None
        ),
        f"recall@{k}": (
            round(sum(recall_scores) / len(recall_scores), 4)
            if recall_scores else None
        ),
        "precision_recall_coverage": len(precision_scores),
        "groundedness": round(
            sum(groundedness_scores)
            / len(groundedness_scores),
            4,
        ),
        "semantic_groundedness": (
            round(sum(semantic_groundedness_scores) / len(semantic_groundedness_scores), 4)
            if semantic_groundedness_scores else None
        ),
        "citation_correctness": round(
            sum(citation_scores)
            / len(citation_scores),
            4,
        ),
        "expert_evaluation": (
            round(
                sum(expert_scores)
                / len(expert_scores),
                4,
            )
            if expert_scores
            else None
        ),
        "number_of_queries": len(results),
    }

    return {
        "summary": summary,
        "results": results,
    }


# ============================================================
# SIMPLE TEST
# ============================================================

if __name__ == "__main__":

    # NOTE: retrieved_documents now carry real passage content (as
    # `retriever.retrieve()` would return), not bare identifiers --
    # this is the fix for the groundedness=0.0 bug. Precision/Recall
    # still match on identity via the "id" field.
    evaluation_data = [
        {
            "question": "What is AES?",

            "answer": (
                "AES is a symmetric block cipher used for "
                "secure encryption [NIST_AES]."
            ),

            "retrieved_documents": [
                {
                    "id": "NIST_AES",
                    "content": (
                        "NIST FIPS 197 specifies the Advanced Encryption "
                        "Standard (AES), a symmetric block cipher used "
                        "for secure encryption of electronic data."
                    ),
                },
                {
                    "id": "CWE_327",
                    "content": (
                        "CWE-327 describes the use of a broken or risky "
                        "cryptographic algorithm as a common software "
                        "weakness."
                    ),
                },
                {
                    "id": "crypto_algorithms",
                    "content": (
                        "An overview of common cryptographic algorithms, "
                        "including AES, RSA, and SHA-256."
                    ),
                },
                {
                    "id": "key_management",
                    "content": (
                        "Key management best practices cover generation, "
                        "distribution, storage, and rotation of "
                        "cryptographic keys."
                    ),
                },
                {
                    "id": "AES_security",
                    "content": (
                        "AES security analysis shows it remains secure "
                        "against all known practical cryptanalytic "
                        "attacks when used with a sufficient key length."
                    ),
                },
            ],

            "relevant_documents": [
                "NIST_AES",
                "AES_security",
            ],

            "expert_scores": {
                "relevance": 5,
                "correctness": 5,
                "completeness": 4,
                "citation_quality": 5,
            },
        }
    ]

    results = evaluate_dataset(
        evaluation_data,
        k=5,
    )

    print("\n========================================")
    print("CryptoSage RAG Evaluation")
    print("========================================")

    print("\nSummary:")

    for metric, value in results["summary"].items():
        print(f"{metric}: {value}")

    print("\n========================================")
