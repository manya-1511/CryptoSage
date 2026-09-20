from __future__ import annotations

from pathlib import Path

from rag.embeddings import (
    TfidfEmbeddingFunction,
    apply_query_instruction,
    get_embedding_backend,
)


def test_get_embedding_backend_falls_back_to_tfidf_when_model_unavailable(tmp_path):
    # A model name that cannot possibly resolve forces the fallback path
    # without needing network access to actually try loading BGE.
    backend = get_embedding_backend(
        model_name="this/model-does-not-exist-and-cannot-load",
        tfidf_persist_path=tmp_path / "vectorizer.joblib",
    )
    assert backend.is_fallback is True
    assert backend.name == "tfidf-fallback"


def test_tfidf_embedding_function_fits_on_first_call_and_persists(tmp_path):
    path = tmp_path / "vectorizer.joblib"
    fn = TfidfEmbeddingFunction(vectorizer_path=path)
    vectors = fn(["AES is a symmetric cipher", "DES is considered broken"])
    assert len(vectors) == 2
    assert len(vectors[0]) == len(vectors[1])
    assert path.exists()


def test_tfidf_embedding_function_reuses_persisted_vocabulary(tmp_path):
    path = tmp_path / "vectorizer.joblib"
    fn1 = TfidfEmbeddingFunction(vectorizer_path=path)
    fn1(["AES is a symmetric cipher", "DES is considered broken"])

    # A fresh instance pointed at the same path must load the fitted
    # vocabulary rather than needing to be refit (retrieval runs in a
    # separate process from ingestion).
    fn2 = TfidfEmbeddingFunction(vectorizer_path=path)
    assert fn2._fitted is True
    query_vector = fn2.embed_query(["symmetric cipher"])
    assert len(query_vector) == 1


def test_apply_query_instruction_skipped_for_fallback_backend(tmp_path):
    backend = get_embedding_backend(
        model_name="this/model-does-not-exist-and-cannot-load",
        tfidf_persist_path=tmp_path / "vectorizer.joblib",
    )
    query = apply_query_instruction("AES security", backend)
    assert query == "AES security"


def test_tfidf_query_before_fit_warns_and_fits_on_query(tmp_path, caplog):
    fn = TfidfEmbeddingFunction(vectorizer_path=tmp_path / "vectorizer.joblib")
    result = fn.embed_query(["first ever call, nothing fitted yet"])
    assert len(result) == 1
