from __future__ import annotations

from rag.evaluation import (
    citation_completeness,
    citation_correctness,
    citation_validity,
    evaluate_dataset,
    evaluate_query,
    groundedness,
    precision_at_k,
    recall_at_k,
)

RETRIEVED = [
    {"id": "NIST_AES", "content": "NIST FIPS 197 specifies AES, a symmetric block cipher for secure encryption.",
     "metadata": {"identifier": "NIST_AES", "title": "AES"}},
    {"id": "CWE_327", "content": "CWE-327 describes the use of a broken or risky cryptographic algorithm.",
     "metadata": {"identifier": "CWE_327", "title": "CWE-327"}},
    {"id": "unrelated_doc", "content": "This document is about firmware update mechanisms in general.",
     "metadata": {"identifier": "unrelated_doc", "title": "Unrelated"}},
]


def test_precision_at_k_basic():
    assert precision_at_k(RETRIEVED, ["NIST_AES", "CWE_327"], k=3) == 2 / 3


def test_precision_at_k_requires_positive_k():
    try:
        precision_at_k(RETRIEVED, ["NIST_AES"], k=0)
        assert False
    except ValueError:
        pass


def test_recall_at_k_basic():
    assert recall_at_k(RETRIEVED, ["NIST_AES", "CWE_327"], k=3) == 1.0


def test_recall_at_k_no_ground_truth_returns_zero_not_error():
    assert recall_at_k(RETRIEVED, [], k=3) == 0.0


def test_recall_at_k_never_exceeds_one_with_duplicate_chunk_ids():
    # Regression test: a chunked knowledge base can return several
    # chunks from the SAME relevant document within the top-K window.
    # recall_at_k must count that document once, not once per chunk,
    # or recall can mathematically exceed 1.0.
    retrieved_with_duplicates = [
        {"id": "NIST_AES", "content": "chunk 1 of the AES standard"},
        {"id": "NIST_AES", "content": "chunk 2 of the AES standard"},
        {"id": "NIST_AES", "content": "chunk 3 of the AES standard"},
    ]
    score = recall_at_k(retrieved_with_duplicates, ["NIST_AES"], k=3)
    assert score == 1.0


def test_precision_at_k_counts_every_chunk_slot_including_duplicates():
    # Unlike recall, precision legitimately counts each retrieved
    # chunk slot -- 3 relevant-document chunks out of 3 total slots
    # retrieved is 100% precision, correctly reflecting that the LLM's
    # limited context was well spent even though it's all one document.
    retrieved_with_duplicates = [
        {"id": "NIST_AES", "content": "chunk 1"},
        {"id": "NIST_AES", "content": "chunk 2"},
        {"id": "unrelated_doc", "content": "chunk 3"},
    ]
    score = precision_at_k(retrieved_with_duplicates, ["NIST_AES"], k=3)
    assert score == 2 / 3


def test_groundedness_high_when_answer_echoes_retrieved_text():
    answer = "AES is a symmetric block cipher for secure encryption specified by NIST."
    score = groundedness(answer, RETRIEVED)
    assert score > 0.0


def test_groundedness_zero_for_empty_context():
    assert groundedness("AES is secure.", []) == 0.0


def test_citation_correctness_loose_match():
    answer = "AES is a symmetric cipher [NIST_AES]."
    assert citation_correctness(answer, RETRIEVED) == 1.0


def test_citation_correctness_zero_when_no_citations_present():
    assert citation_correctness("AES is a symmetric cipher.", RETRIEVED) == 0.0


def test_citation_validity_strict_matches_actual_retrieved_labels():
    answer = "AES is a symmetric cipher [NIST_AES]."
    assert citation_validity(answer, RETRIEVED) == 1.0


def test_citation_validity_rejects_fabricated_label():
    answer = "AES is a symmetric cipher [TOTALLY_MADE_UP]."
    assert citation_validity(answer, RETRIEVED) == 0.0


def test_citation_completeness_flags_uncited_factual_sentence():
    answer = "AES is a symmetric block cipher standard [NIST_AES]. It was adopted worldwide for many use cases."
    score = citation_completeness(answer)
    assert 0.0 < score < 1.0


def test_citation_completeness_vacuously_complete_with_no_factual_sentences():
    assert citation_completeness("") == 0.0
    assert citation_completeness("OK.") == 1.0


def test_evaluate_query_returns_none_precision_without_ground_truth():
    result = evaluate_query("What is AES?", "AES is a cipher [NIST_AES].", RETRIEVED, relevant_documents=None)
    assert result["metrics"]["precision_at_k"] is None
    assert result["metrics"]["recall_at_k"] is None
    assert result["metrics"]["ground_truth_available"] is False


def test_evaluate_query_reports_latencies_verbatim_when_provided():
    result = evaluate_query(
        "What is AES?", "AES is a cipher [NIST_AES].", RETRIEVED, relevant_documents=["NIST_AES"],
        latencies_ms={"retrieval_time_ms": 12.3, "llm_generation_time_ms": 400.5, "total_generation_time_ms": 412.8},
    )
    assert result["metrics"]["retrieval_time_ms"] == 12.3
    assert result["metrics"]["total_generation_time_ms"] == 412.8


def test_evaluate_dataset_aggregate_precision_none_without_any_ground_truth():
    dataset = [
        {"question": "Q1", "answer": "AES is a cipher [NIST_AES].", "retrieved_documents": RETRIEVED, "relevant_documents": []},
    ]
    result = evaluate_dataset(dataset, k=3)
    assert result["summary"]["precision@3"] is None
    assert result["summary"]["precision_recall_coverage"] == 0


def test_evaluate_dataset_empty_raises():
    try:
        evaluate_dataset([])
        assert False
    except ValueError:
        pass
