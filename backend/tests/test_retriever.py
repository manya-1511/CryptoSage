from __future__ import annotations

import pytest

from rag.retriever import RetrieverError, retrieve, rerank


def test_retrieve_raises_on_never_ingested_collection(tmp_path):
    from config import get_settings

    empty_dir = tmp_path / "never_ingested"
    with pytest.raises(RetrieverError):
        retrieve("AES symmetric algorithm security", persist_dir=empty_dir)


def test_retrieve_returns_results_for_ingested_kb(ingested_kb):
    results = retrieve("AES symmetric block cipher security", persist_dir=ingested_kb["persist_dir"])
    assert len(results) > 0
    assert all("content" in r and "metadata" in r and "similarity" in r and "distance" in r for r in results)


def test_retrieve_respects_top_k(ingested_kb):
    results = retrieve("cryptographic algorithm security key management", persist_dir=ingested_kb["persist_dir"], top_k=2)
    assert len(results) <= 2


def test_retrieve_empty_query_does_not_crash(ingested_kb):
    # An empty query string is a degenerate but valid input -- retrieval
    # must not raise, even if the results are low quality.
    results = retrieve("", persist_dir=ingested_kb["persist_dir"])
    assert isinstance(results, list)


def test_rerank_empty_candidates_returns_empty():
    assert rerank([]) == []


def test_rerank_boosts_algorithm_keyword_match():
    candidates = [
        {"content": "Generic advice about key rotation and storage.", "metadata": {"title": "SP 800-57"}, "similarity": 0.5},
        {"content": "AES is a symmetric block cipher standardized by NIST.", "metadata": {"title": "FIPS 197"}, "similarity": 0.5},
    ]
    reranked = rerank(candidates, algorithm="AES", algorithm_family="symmetric", top_k=2)
    # Same starting similarity, but the AES-relevant chunk should rank
    # first because of the algorithm_match term.
    assert reranked[0]["metadata"]["title"] == "FIPS 197"
    assert reranked[0]["rerank_score"] > reranked[1]["rerank_score"]


def test_rerank_respects_top_k_truncation():
    candidates = [{"content": f"chunk {i}", "metadata": {}, "similarity": 0.1 * i} for i in range(10)]
    reranked = rerank(candidates, top_k=3)
    assert len(reranked) == 3


def test_rerank_never_invents_new_candidates():
    candidates = [{"content": "AES chunk", "metadata": {"title": "FIPS 197"}, "similarity": 0.9}]
    reranked = rerank(candidates, algorithm="AES", top_k=5)
    # top_k larger than candidate pool must not fabricate extra results.
    assert len(reranked) == 1


def test_retrieve_reranking_uses_risk_factor_context(ingested_kb):
    results = retrieve(
        "cryptographic algorithm security",
        persist_dir=ingested_kb["persist_dir"],
        algorithm="AES",
        risk_factors=["broken_algorithm"],
        top_k=3,
    )
    assert all("rerank_score" in r for r in results)
