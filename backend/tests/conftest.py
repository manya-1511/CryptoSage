from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def _reset_caches(monkeypatch, tmp_path):
    """Every test gets its own ChromaDB persist dir and a cold
    embedding-backend cache, so tests never see another test's
    ingested collection or TF-IDF vocabulary.
    """
    monkeypatch.setenv("RAG_CHROMA_PERSIST_DIR", str(tmp_path / "chroma_store"))
    from config import get_settings

    get_settings.cache_clear()

    import rag.retriever as retriever

    retriever._get_embedding_backend_cached.cache_clear()
    yield
    get_settings.cache_clear()
    retriever._get_embedding_backend_cached.cache_clear()


@pytest.fixture
def knowledge_base_dir(tmp_path):
    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()

    (kb_dir / "fips197.md").write_text(
        "---\n"
        "title: NIST FIPS 197 - Advanced Encryption Standard (AES)\n"
        "source_type: NIST\n"
        "identifier: FIPS 197\n"
        "---\n"
        "# Advanced Encryption Standard\n\n"
        "## Overview\n\n"
        "AES is a symmetric block cipher established by NIST in FIPS 197. "
        "It supports 128, 192, or 256 bit keys.\n\n"
        "## Security Properties\n\n"
        "AES is considered secure against all known practical cryptanalytic "
        "attacks when implemented correctly.\n",
        encoding="utf-8",
    )

    (kb_dir / "cwe327.md").write_text(
        "---\n"
        "title: CWE-327 - Use of a Broken or Risky Cryptographic Algorithm\n"
        "source_type: MITRE\n"
        "identifier: CWE-327\n"
        "---\n"
        "# Use of a Broken or Risky Cryptographic Algorithm\n\n"
        "The product uses a broken or risky cryptographic algorithm. "
        "DES, RC4, and MD5 are considered broken or risky.\n",
        encoding="utf-8",
    )

    (kb_dir / "sp80057.md").write_text(
        "---\n"
        "title: NIST SP 800-57 - Key Management Recommendations\n"
        "source_type: NIST\n"
        "identifier: SP 800-57\n"
        "---\n"
        "# Recommendation for Key Management\n\n"
        "NIST SP 800-57 provides guidance on cryptographic key generation, "
        "distribution, storage, rotation, and destruction.\n",
        encoding="utf-8",
    )

    return kb_dir


@pytest.fixture
def ingested_kb(knowledge_base_dir, tmp_path):
    """Ingest the sample knowledge base into a fresh ChromaDB store and
    return the persist dir used, so retrieval tests can point at it.
    """
    from config import get_settings
    from rag.ingest import ingest_knowledge_base

    settings = get_settings()
    summary = ingest_knowledge_base(knowledge_base_dir=knowledge_base_dir, persist_dir=settings.RAG_CHROMA_PERSIST_DIR)
    return {"persist_dir": settings.RAG_CHROMA_PERSIST_DIR, "summary": summary}
