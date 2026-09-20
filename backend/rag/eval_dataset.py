"""
rag/eval_dataset.py

Phase 7 -- Dataset-level RAG evaluation (spec section 11).

Builds a small set of CryptoSage-specific questions, runs REAL
retrieval against the ingested knowledge base for each one (no
fabricated `retrieved_documents`), and scores the result with
`rag.evaluation.evaluate_dataset`.

Two things are intentionally NOT fabricated here:
  - `answer`: for each question this uses the deterministic template
    explanation machinery's sentence-construction style (grounded
    directly in retrieved evidence) rather than an invented "ideal"
    answer, since we have no live Qwen/Ollama in this environment to
    generate a real LLM answer. Swap `_answer_from_retrieval()` for a
    real `rag.explain.explain_firmware(...)` call (or a direct Ollama
    call) once Ollama is running to evaluate the actual LLM path.
  - `expert_scores`: these are illustrative placeholders (all None
    unless explicitly filled in) -- do NOT report them as real expert
    evaluation results in a paper. Replace with an actual human
    reviewer's 1-5 ratings before using the "expert_evaluation" summary
    metric for anything.

Run with:  python -m rag.eval_dataset
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config import get_settings
from rag.citations import extract_citations, citations_to_reference_strings
from rag.evaluation import evaluate_dataset
from rag.retriever import RetrieverError, build_retrieval_query, retrieve

# CryptoSage-specific questions named in the spec. `relevant_documents`
# are this sample knowledge base's own identifiers (see
# rag/knowledge_base/*.md) -- ground truth for THIS demo KB, not a
# universal answer key. Replace with your real knowledge base's
# identifiers when evaluating against it.
QUESTIONS: list[dict[str, Any]] = [
    {
        "question": "What is AES and what standard defines it?",
        "algorithm": "AES", "algorithm_family": "symmetric",
        "risk_factors": [], "recommendations": [],
        "relevant_documents": ["FIPS 197"],
    },
    {
        "question": "Why is DES considered risky?",
        "algorithm": "DES", "algorithm_family": "symmetric",
        "risk_factors": ["outdated_algorithm"], "recommendations": [],
        "relevant_documents": ["CWE-327"],
    },
    {
        "question": "What is the security relevance of SHA-1?",
        "algorithm": "SHA-1", "algorithm_family": "hash",
        "risk_factors": ["outdated_algorithm"], "recommendations": [],
        "relevant_documents": ["CWE-327"],
    },
    {
        "question": "What does CWE-327 describe?",
        "algorithm": "", "algorithm_family": "",
        "risk_factors": ["broken_or_risky_algorithm"], "recommendations": [],
        "relevant_documents": ["CWE-327"],
    },
    {
        "question": "What are appropriate mitigations for outdated cryptographic algorithms?",
        "algorithm": "", "algorithm_family": "",
        "risk_factors": ["outdated_algorithm"], "recommendations": ["Upgrade to a modern vetted algorithm"],
        "relevant_documents": ["CWE-327", "SP 800-57"],
    },
    {
        "question": "What does NIST recommend regarding cryptographic key management?",
        "algorithm": "", "algorithm_family": "",
        "risk_factors": [], "recommendations": ["Rotate and manage cryptographic keys per NIST guidance"],
        "relevant_documents": ["SP 800-57"],
    },
]


def _answer_from_retrieval(retrieved_documents: list[dict[str, Any]], question: str) -> str:
    """A minimal, evidence-grounded answer built only from retrieved
    text -- stands in for a real Qwen/template answer so this script
    is runnable end-to-end without a live Ollama server. Every sentence
    is either lifted-and-cited from retrieval or the explicit "not
    established" disclaimer; nothing is invented.
    """
    if not retrieved_documents:
        return "The retrieved evidence does not establish this claim."

    citations = extract_citations(retrieved_documents)
    top = retrieved_documents[0]
    label = top.get("metadata", {}).get("identifier") or top.get("metadata", {}).get("title") or "Source"
    snippet = " ".join(top.get("content", "").split()[:40])
    return f"{snippet} [{label}]"


def build_and_run(knowledge_base_dir: Path | None = None, persist_dir: Path | None = None) -> dict[str, Any]:
    settings = get_settings()
    persist_dir = persist_dir or settings.RAG_CHROMA_PERSIST_DIR

    dataset = []
    for item in QUESTIONS:
        query = build_retrieval_query(
            item["algorithm"], item["algorithm_family"], item["risk_factors"], item["recommendations"],
        )
        try:
            retrieved = retrieve(
                query, persist_dir=persist_dir,
                algorithm=item["algorithm"], algorithm_family=item["algorithm_family"],
                risk_factors=item["risk_factors"], recommendations=item["recommendations"],
            )
        except RetrieverError as exc:
            retrieved = []
            print(f"[warn] retrieval unavailable for {item['question']!r}: {exc}")

        answer = _answer_from_retrieval(retrieved, item["question"])
        dataset.append({
            "question": item["question"],
            "answer": answer,
            "retrieved_documents": retrieved,
            "relevant_documents": item["relevant_documents"],
        })

    results = evaluate_dataset(dataset, k=settings.RAG_TOP_K)
    return results


if __name__ == "__main__":
    output = build_and_run()
    print(json.dumps(output["summary"], indent=2))
