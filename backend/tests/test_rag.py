"""
tests/test_rag.py

Unit tests for the rag/ package.

Does NOT require Ollama to be running (HTTP calls are mocked) and does
NOT require the BGE model weights to be downloaded (embedding backend
loading is monkeypatched/mocked in every test that isn't specifically
exercising the TF-IDF fallback path). Uses only plain unittest +
unittest.mock, no pytest plugins, so it runs in a minimal environment.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from rag import citations as citations_mod  # noqa: E402
from rag import evaluation  # noqa: E402
from rag import ingest  # noqa: E402
from rag.embeddings import (  # noqa: E402
    BGE_QUERY_INSTRUCTION,
    EmbeddingBackend,
    EmbeddingBackendError,
    TfidfEmbeddingFunction,
    apply_query_instruction,
    get_embedding_backend,
)


# ============================================================
# 1. RECURSIVE DOCUMENT DISCOVERY
# ============================================================

class TestRecursiveDiscovery(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp())
        (self.tmp_dir / "nist").mkdir()
        (self.tmp_dir / "cwe" / "nested").mkdir(parents=True)
        (self.tmp_dir / "nist" / "fips197.md").write_text("---\ntitle: FIPS 197\n---\nAES content.")
        (self.tmp_dir / "cwe" / "nested" / "cwe327.md").write_text("---\ntitle: CWE-327\n---\nWeak crypto.")
        (self.tmp_dir / "root_doc.txt").write_text("Root-level doc with no front matter.")
        (self.tmp_dir / "ignored.json").write_text("{}")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_discovers_nested_files(self) -> None:
        docs = ingest.discover_documents(self.tmp_dir)
        names = {d.name for d in docs}
        self.assertIn("fips197.md", names)
        self.assertIn("cwe327.md", names)
        self.assertIn("root_doc.txt", names)
        self.assertNotIn("ignored.json", names)

    def test_missing_directory_returns_empty_not_raise(self) -> None:
        docs = ingest.discover_documents(self.tmp_dir / "does_not_exist")
        self.assertEqual(docs, [])


# ============================================================
# 2 & 3. FRONT-MATTER PARSING AND METADATA PRESERVATION
# ============================================================

class TestParseDocument(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp())
        (self.tmp_dir / "nist").mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_full_front_matter_parsed_and_source_category_derived(self) -> None:
        path = self.tmp_dir / "nist" / "fips197.md"
        path.write_text(
            "---\n"
            "title: NIST FIPS 197\n"
            "source_type: NIST\n"
            "identifier: FIPS_197\n"
            "source_url: https://csrc.nist.gov/pubs/fips/197/final\n"
            "publisher: NIST\n"
            "---\n"
            "AES is a symmetric block cipher."
        )
        parsed = ingest.parse_document(path, self.tmp_dir)
        self.assertEqual(parsed["title"], "NIST FIPS 197")
        self.assertEqual(parsed["source_type"], "NIST")
        self.assertEqual(parsed["identifier"], "FIPS_197")
        self.assertEqual(parsed["source_category"], "nist")
        self.assertEqual(parsed["source_file"], "nist/fips197.md")
        self.assertEqual(parsed["source_url"], "https://csrc.nist.gov/pubs/fips/197/final")
        self.assertEqual(parsed["publisher"], "NIST")
        self.assertNotIn("publication_date", parsed)  # never fabricated when absent

    def test_missing_front_matter_still_ingested(self) -> None:
        path = self.tmp_dir / "root.txt"
        path.write_text("Just plain content, no front matter.")
        parsed = ingest.parse_document(path, self.tmp_dir)
        self.assertEqual(parsed["content"], "Just plain content, no front matter.")
        self.assertEqual(parsed["source_type"], "Unknown")
        self.assertEqual(parsed["source_category"], "")


# ============================================================
# 4. CHUNKING
# ============================================================

class TestChunking(unittest.TestCase):
    def test_chunk_document_respects_size(self) -> None:
        content = "Sentence one. " * 200
        chunks = ingest.chunk_document(content, chunk_size=200, chunk_overlap=20)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 250)  # some slack for boundary rules

    def test_short_content_single_chunk(self) -> None:
        chunks = ingest.chunk_document("Short content.", chunk_size=800, chunk_overlap=100)
        self.assertEqual(len(chunks), 1)


# ============================================================
# 5. BGE QUERY INSTRUCTION
# ============================================================

class TestBgeQueryInstruction(unittest.TestCase):
    def test_instruction_applied_for_bge(self) -> None:
        backend = EmbeddingBackend(embed=lambda x: x, name="BAAI/bge-small-en-v1.5", is_fallback=False)
        result = apply_query_instruction("AES symmetric cipher", backend)
        self.assertTrue(result.startswith(BGE_QUERY_INSTRUCTION))

    def test_instruction_skipped_for_tfidf(self) -> None:
        backend = EmbeddingBackend(embed=lambda x: x, name="tfidf-fallback", is_fallback=True)
        result = apply_query_instruction("AES symmetric cipher", backend)
        self.assertEqual(result, "AES symmetric cipher")


# ============================================================
# 6. TF-IDF FALLBACK BEHAVIOR
# ============================================================

class TestTfidfFallback(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_falls_back_when_bge_unavailable_and_not_strict(self) -> None:
        with patch("rag.embeddings._try_load_sentence_transformer", return_value=None):
            backend = get_embedding_backend(
                "BAAI/bge-small-en-v1.5",
                tfidf_persist_path=self.tmp_dir / "vec.joblib",
                strict=False,
                allow_tfidf_fallback=True,
            )
        self.assertTrue(backend.is_fallback)
        self.assertEqual(backend.name, "tfidf-fallback")

    def test_strict_mode_raises_instead_of_falling_back(self) -> None:
        with patch("rag.embeddings._try_load_sentence_transformer", return_value=None):
            with self.assertRaises(EmbeddingBackendError):
                get_embedding_backend(
                    "BAAI/bge-small-en-v1.5",
                    tfidf_persist_path=self.tmp_dir / "vec.joblib",
                    strict=True,
                )

    def test_fallback_disabled_raises(self) -> None:
        with patch("rag.embeddings._try_load_sentence_transformer", return_value=None):
            with self.assertRaises(EmbeddingBackendError):
                get_embedding_backend(
                    "BAAI/bge-small-en-v1.5",
                    tfidf_persist_path=self.tmp_dir / "vec.joblib",
                    strict=False,
                    allow_tfidf_fallback=False,
                )

    def test_tfidf_vectorizer_persists_and_reloads(self) -> None:
        vec_path = self.tmp_dir / "vec.joblib"
        fn1 = TfidfEmbeddingFunction(vectorizer_path=vec_path)
        vectors1 = fn1(["AES symmetric cipher", "RSA asymmetric cipher"])
        self.assertTrue(vec_path.exists())

        fn2 = TfidfEmbeddingFunction(vectorizer_path=vec_path)
        vectors2 = fn2.embed_query(["AES symmetric cipher"])
        self.assertEqual(len(vectors1[0]), len(vectors2[0]))


# ============================================================
# 7. EMBEDDING BACKEND MISMATCH DETECTION
# ============================================================

class TestBackendMismatchDetection(unittest.TestCase):
    def test_mismatch_raises_retriever_error(self) -> None:
        from rag.retriever import RetrieverError, get_collection

        fake_collection = MagicMock()
        fake_collection.metadata = {"embedding_backend": "BAAI/bge-small-en-v1.5"}
        fake_client = MagicMock()
        fake_client.get_collection.return_value = fake_collection

        active_backend = EmbeddingBackend(embed=lambda x: x, name="tfidf-fallback", is_fallback=True)

        tmp_dir = Path(tempfile.mkdtemp())
        try:
            with patch("chromadb.PersistentClient", return_value=fake_client):
                with self.assertRaises(RetrieverError):
                    get_collection(persist_dir=tmp_dir, embedding_backend=active_backend)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_matching_backend_does_not_raise(self) -> None:
        from rag.retriever import get_collection

        fake_collection = MagicMock()
        fake_collection.metadata = {"embedding_backend": "tfidf-fallback"}
        fake_client = MagicMock()
        fake_client.get_collection.return_value = fake_collection

        active_backend = EmbeddingBackend(embed=lambda x: x, name="tfidf-fallback", is_fallback=True)

        tmp_dir = Path(tempfile.mkdtemp())
        try:
            with patch("chromadb.PersistentClient", return_value=fake_client):
                collection = get_collection(persist_dir=tmp_dir, embedding_backend=active_backend)
            self.assertIs(collection, fake_collection)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


# ============================================================
# 8. RETRIEVAL RESULT STRUCTURE
# ============================================================

class TestRetrievalResultStructure(unittest.TestCase):
    def test_retrieve_returns_content_metadata_distance_similarity(self) -> None:
        from rag.retriever import retrieve

        fake_collection = MagicMock()
        fake_collection.metadata = {"embedding_backend": "tfidf-fallback", "distance_metric": "cosine"}
        fake_collection.query.return_value = {
            "documents": [["AES is a symmetric block cipher."]],
            "metadatas": [[{"identifier": "FIPS_197", "document_id": "FIPS_197"}]],
            "distances": [[0.12]],
        }
        active_backend = EmbeddingBackend(embed=lambda x: x, name="tfidf-fallback", is_fallback=True)

        with patch("rag.retriever._get_embedding_backend_cached", return_value=active_backend):
            with patch("rag.retriever.get_collection", return_value=fake_collection):
                results = retrieve("AES security", top_k=1)

        self.assertEqual(len(results), 1)
        record = results[0]
        self.assertEqual(record["content"], "AES is a symmetric block cipher.")
        self.assertEqual(record["metadata"]["identifier"], "FIPS_197")
        self.assertAlmostEqual(record["distance"], 0.12)
        self.assertAlmostEqual(record["similarity"], 0.88)
        self.assertEqual(record["similarity_metric"], "cosine")

    def test_empty_results_returns_empty_list_not_raise(self) -> None:
        from rag.retriever import retrieve

        fake_collection = MagicMock()
        fake_collection.metadata = {"embedding_backend": "tfidf-fallback"}
        fake_collection.query.return_value = {"documents": [[]], "metadatas": [[]], "distances": [[]]}
        active_backend = EmbeddingBackend(embed=lambda x: x, name="tfidf-fallback", is_fallback=True)

        with patch("rag.retriever._get_embedding_backend_cached", return_value=active_backend):
            with patch("rag.retriever.get_collection", return_value=fake_collection):
                results = retrieve("nonexistent query", top_k=3)
        self.assertEqual(results, [])


# ============================================================
# 9 & 10. CITATION EXTRACTION AND FABRICATED-CITATION REJECTION
# ============================================================

class TestCitationValidation(unittest.TestCase):
    def setUp(self) -> None:
        self.retrieved = [
            {"content": "AES text", "metadata": {"identifier": "FIPS_197", "document_id": "FIPS_197", "title": "NIST FIPS 197", "source_type": "NIST"}},
            {"content": "CWE text", "metadata": {"identifier": "CWE_327", "document_id": "CWE_327", "title": "CWE-327", "source_type": "MITRE"}},
        ]

    def test_extract_citations_deduplicates(self) -> None:
        cites = citations_mod.extract_citations(self.retrieved + [self.retrieved[0]])
        self.assertEqual(len(cites), 2)

    def test_valid_citation_accepted(self) -> None:
        answer = "AES is defined by NIST [FIPS_197]."
        result = citations_mod.validate_answer_citations(answer, self.retrieved)
        self.assertEqual(result.valid_ids, ["FIPS_197"])
        self.assertEqual(result.invalid_ids, [])
        self.assertTrue(result.all_valid)

    def test_fabricated_citation_rejected(self) -> None:
        answer = "This is protected under CVE-2024-99999 [CVE_2024_99999]."
        result = citations_mod.validate_answer_citations(answer, self.retrieved)
        self.assertEqual(result.invalid_ids, ["CVE_2024_99999"])
        self.assertFalse(result.all_valid)

    def test_substring_of_real_id_is_not_accepted(self) -> None:
        # "FIPS" alone is a substring of "FIPS_197" but must NOT validate --
        # exact match only, no fuzzy/substring acceptance.
        answer = "See [FIPS] for details."
        result = citations_mod.validate_answer_citations(answer, self.retrieved)
        self.assertEqual(result.invalid_ids, ["FIPS"])

    def test_source_id_prefix_stripped(self) -> None:
        answer = "See [SOURCE_ID: FIPS_197] for details."
        ids = citations_mod.extract_answer_citation_ids(answer)
        self.assertEqual(ids, ["FIPS_197"])


# ============================================================
# 11 & 12. PRECISION@K / RECALL@K
# ============================================================

class TestPrecisionRecall(unittest.TestCase):
    def test_precision_at_k_matches_standard_definition(self) -> None:
        retrieved = ["A", "B", "C", "D", "E"]
        relevant = ["A", "C", "F"]
        self.assertAlmostEqual(evaluation.precision_at_k(retrieved, relevant, k=5), 2 / 5)

    def test_recall_at_k_matches_standard_definition(self) -> None:
        retrieved = ["A", "B", "C", "D", "E"]
        relevant = ["A", "C", "F"]
        self.assertAlmostEqual(evaluation.recall_at_k(retrieved, relevant, k=5), 2 / 3)

    def test_precision_recall_with_dict_documents(self) -> None:
        retrieved = [{"id": "NIST_AES"}, {"id": "CWE_327"}]
        relevant = ["NIST_AES"]
        self.assertAlmostEqual(evaluation.precision_at_k(retrieved, relevant, k=2), 0.5)
        self.assertAlmostEqual(evaluation.recall_at_k(retrieved, relevant, k=2), 1.0)


# ============================================================
# 13. LEXICAL GROUNDEDNESS
# ============================================================

class TestGroundedness(unittest.TestCase):
    def test_groundedness_uses_content_not_bare_ids(self) -> None:
        # Regression test for the documented bug: bare identifiers must
        # NOT silently produce groundedness == 0.0 forever; passing real
        # content must produce a nonzero score for a supported claim.
        answer = "AES is a symmetric block cipher used for secure encryption."
        context_as_ids_only = ["NIST_AES"]
        context_with_content = [{
            "id": "NIST_AES",
            "content": "NIST FIPS 197 specifies AES, a symmetric block cipher used for secure encryption.",
        }]
        score_ids_only = evaluation.groundedness(answer, context_as_ids_only)
        score_with_content = evaluation.groundedness(answer, context_with_content)
        self.assertGreater(score_with_content, score_ids_only)
        self.assertGreater(score_with_content, 0.0)

    def test_empty_answer_or_context_returns_zero(self) -> None:
        self.assertEqual(evaluation.groundedness("", ["some context"]), 0.0)
        self.assertEqual(evaluation.groundedness("some answer.", []), 0.0)

    def test_semantic_groundedness_returns_none_without_backend(self) -> None:
        result = evaluation.semantic_groundedness(
            "AES is secure.", [{"content": "AES is a secure cipher."}], embedding_backend=None,
        )
        # No real backend importable/available in this unit-test context
        # (or it's the TF-IDF fallback) -- must be None, never a fabricated number.
        self.assertIsNone(result) if result is not None else None  # smoke: must not raise

    def test_semantic_groundedness_none_for_tfidf_backend(self) -> None:
        tfidf_backend = EmbeddingBackend(embed=lambda x: x, name="tfidf-fallback", is_fallback=True)
        result = evaluation.semantic_groundedness(
            "AES is secure.", [{"content": "AES is a secure cipher."}], embedding_backend=tfidf_backend,
        )
        self.assertIsNone(result)


# ============================================================
# 14. CITATION CORRECTNESS (evaluation.py's separate, looser metric)
# ============================================================

class TestCitationCorrectnessMetric(unittest.TestCase):
    def test_correct_citation(self) -> None:
        answer = "AES is a symmetric cipher [NIST_AES]."
        docs = ["NIST_AES", "CWE_327"]
        self.assertEqual(evaluation.citation_correctness(answer, docs), 1.0)

    def test_no_citations_returns_zero(self) -> None:
        self.assertEqual(evaluation.citation_correctness("No citations here.", ["NIST_AES"]), 0.0)


# ============================================================
# 15. TEMPLATE FALLBACK
# ============================================================

class TestTemplateFallback(unittest.TestCase):
    def test_template_fallback_never_invents_citations(self) -> None:
        from rag.explain import generate_template_explanation

        sections = generate_template_explanation(
            algorithm="AES", algorithm_family="Symmetric", confidence=91.2, risk_score=42.0,
            risk_level="Medium", risk_factors=[{"factor": "weak_key_size", "contribution": 10}],
            recommendations=["Use AES-256"], retrieved_documents=[],
        )
        self.assertIn("no supporting documents were retrieved", sections["Referenced Standards"])

    def test_template_fallback_cites_only_retrieved_docs(self) -> None:
        from rag.explain import generate_template_explanation

        retrieved = [{"content": "x", "metadata": {"identifier": "FIPS_197", "title": "NIST FIPS 197", "source_type": "NIST"}}]
        sections = generate_template_explanation(
            algorithm="AES", algorithm_family="Symmetric", confidence=91.2, risk_score=42.0,
            risk_level="Medium", risk_factors=[], recommendations=[], retrieved_documents=retrieved,
        )
        self.assertIn("FIPS_197", sections["Referenced Standards"])


# ============================================================
# 16. OLLAMA UNAVAILABLE BEHAVIOR (mocked HTTP, no real Ollama needed)
# ============================================================

class TestOllamaUnavailable(unittest.TestCase):
    def test_is_available_false_on_connection_error(self) -> None:
        from rag.explain import OllamaClient
        import requests

        client = OllamaClient(base_url="http://localhost:11434")
        with patch("requests.get", side_effect=requests.exceptions.ConnectionError):
            self.assertFalse(client.is_available())

    def test_generate_returns_none_on_failure(self) -> None:
        from rag.explain import OllamaClient
        import requests

        client = OllamaClient(base_url="http://localhost:11434")
        with patch("requests.post", side_effect=requests.exceptions.Timeout):
            self.assertIsNone(client.generate("prompt"))

    def test_explain_firmware_uses_template_fallback_when_ollama_down(self) -> None:
        from rag.explain import explain_firmware

        with patch("rag.explain.OllamaClient.is_available", return_value=False):
            with patch("rag.explain.retrieve", return_value=[]):
                result = explain_firmware(
                    firmware_id=1,
                    firmware_metadata={"filename": "fw.bin", "file_hash": "abc", "upload_time": "now"},
                    feature_vector={"architecture": "ARM"},
                    algorithm="AES", algorithm_family="Symmetric", confidence=88.0,
                    risk_score=20.0, risk_level="Low",
                    risk_factors=[], recommendations=[],
                )
        self.assertEqual(result.generated_by, "template_fallback")
        self.assertEqual(result.invalid_citations, [])  # template never fabricates citations
        self.assertFalse(result.used_fast_model)  # default: never silently opts into the fast model

    def test_fast_model_never_used_unless_explicitly_requested(self) -> None:
        from rag.explain import explain_firmware, OllamaClient

        captured_models: list[str] = []
        original_init = OllamaClient.__init__

        def _capturing_init(self, base_url=None, model=None, timeout=None):
            captured_models.append(model)
            original_init(self, base_url=base_url, model=model, timeout=timeout)

        with patch("rag.explain.OllamaClient.__init__", _capturing_init):
            with patch("rag.explain.OllamaClient.is_available", return_value=False):
                with patch("rag.explain.retrieve", return_value=[]):
                    result = explain_firmware(
                        firmware_id=2,
                        firmware_metadata={"filename": "fw.bin", "file_hash": "abc", "upload_time": "now"},
                        feature_vector={"architecture": "ARM"},
                        algorithm="AES", algorithm_family="Symmetric", confidence=88.0,
                        risk_score=20.0, risk_level="Low",
                        risk_factors=[], recommendations=[],
                        # use_fast_model intentionally omitted -- must default to the reported model
                    )
        from config import get_settings
        self.assertEqual(captured_models, [get_settings().OLLAMA_MODEL])
        self.assertFalse(result.used_fast_model)

    def test_fast_model_used_and_recorded_when_explicitly_requested(self) -> None:
        from rag.explain import explain_firmware
        from config import get_settings

        with patch("rag.explain.OllamaClient.is_available", return_value=False):
            with patch("rag.explain.retrieve", return_value=[]):
                result = explain_firmware(
                    firmware_id=3,
                    firmware_metadata={"filename": "fw.bin", "file_hash": "abc", "upload_time": "now"},
                    feature_vector={"architecture": "ARM"},
                    algorithm="AES", algorithm_family="Symmetric", confidence=88.0,
                    risk_score=20.0, risk_level="Low",
                    risk_factors=[], recommendations=[],
                    use_fast_model=True,
                )
        self.assertTrue(result.used_fast_model)
        # Even though Ollama was "down" here (template fallback used), the
        # fast-model choice itself must still be visible/traceable on the result.
        self.assertEqual(result.generated_by, "template_fallback")


if __name__ == "__main__":
    unittest.main()
