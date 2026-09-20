"""
rag/embeddings.py

Phase 7 -- Embedding generation for the RAG knowledge base.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from chromadb.api.types import Documents, Embeddings
from chromadb.utils.embedding_functions import EmbeddingFunction

logger = logging.getLogger("cryptosage.rag.embeddings")

BGE_MODEL_NAME = "BAAI/bge-small-en-v1.5"
BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


@dataclass
class EmbeddingBackend:
    embed: Any
    name: str
    is_fallback: bool


class SentenceTransformerEmbeddingFunction(EmbeddingFunction):
    def __init__(self, model: Any) -> None:
        self._model = model

    def __call__(self, input: Documents) -> Embeddings:  # noqa: A002
        embeddings = self._model.encode(list(input), normalize_embeddings=True)
        return [vector.tolist() for vector in embeddings]

    def name(self) -> str:
        return BGE_MODEL_NAME


class TfidfEmbeddingFunction(EmbeddingFunction):
    def __init__(self, max_features: int = 4096, vectorizer_path: Optional[Any] = None) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer

        self._vectorizer_path = vectorizer_path
        self._fitted = False

        if vectorizer_path is not None and Path(vectorizer_path).exists():
            import joblib

            self._vectorizer = joblib.load(vectorizer_path)
            self._fitted = True
            logger.info("Loaded persisted TF-IDF vectorizer from %s", vectorizer_path)
        else:
            self._vectorizer = TfidfVectorizer(max_features=max_features, stop_words="english")

    def __call__(self, input: Documents) -> Embeddings:  # noqa: A002
        texts = list(input)
        if not self._fitted:
            matrix = self._vectorizer.fit_transform(texts)
            self._fitted = True
            self._persist()
        else:
            matrix = self._vectorizer.transform(texts)
        return matrix.toarray().tolist()

    def embed_query(self, input: Documents) -> Embeddings:  # noqa: A002
        if not self._fitted:
            logger.warning(
                "TF-IDF embedding function queried before being fit on any documents "
                "(knowledge base not yet ingested); falling back to fit-on-query."
            )
            return self.__call__(input)
        return self._vectorizer.transform(list(input)).toarray().tolist()

    def _persist(self) -> None:
        if self._vectorizer_path is None:
            return
        import joblib

        Path(self._vectorizer_path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self._vectorizer, self._vectorizer_path)
        logger.info("Persisted fitted TF-IDF vectorizer to %s", self._vectorizer_path)

    def name(self) -> str:
        return "tfidf-fallback"

    def get_config(self) -> dict[str, Any]:
        # Newer ChromaDB versions expect every custom EmbeddingFunction
        # to implement this for (de)serialization support; the TF-IDF
        # vectorizer itself is persisted separately via joblib (see
        # `_persist`), so there is no extra config to round-trip here.
        return {}


def _try_load_sentence_transformer(model_name: str, timeout_seconds: int = 60) -> Optional[Any]:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        logger.warning("sentence-transformers is not installed; falling back to TF-IDF embeddings.")
        return None

    import threading

    result: dict[str, Any] = {}

    def _load() -> None:
        try:
            result["model"] = SentenceTransformer(model_name)
        except Exception as exc:  # noqa: BLE001
            result["error"] = exc

    thread = threading.Thread(target=_load, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)

    if thread.is_alive():
        logger.warning(
            "Loading embedding model '%s' did not complete within %ds (likely no network "
            "access to the Hugging Face Hub); falling back to local TF-IDF embeddings. "
            "Install/cache the model in this environment to use real semantic embeddings.",
            model_name, timeout_seconds,
        )
        return None

    if "error" in result:
        logger.warning(
            "Could not load embedding model '%s' (%s); falling back to local TF-IDF embeddings.",
            model_name, result["error"],
        )
        return None

    return result.get("model")


def get_embedding_backend(model_name: str = BGE_MODEL_NAME, tfidf_persist_path: Optional[Path] = None) -> EmbeddingBackend:
    model = _try_load_sentence_transformer(model_name)
    if model is not None:
        logger.info("Embedding backend: sentence-transformers ('%s').", model_name)
        return EmbeddingBackend(embed=SentenceTransformerEmbeddingFunction(model), name=model_name, is_fallback=False)

    if tfidf_persist_path is None:
        from config import get_settings

        tfidf_persist_path = get_settings().RAG_CHROMA_PERSIST_DIR / "tfidf_vectorizer.joblib"

    fallback = TfidfEmbeddingFunction(vectorizer_path=tfidf_persist_path)
    logger.info("Embedding backend: TF-IDF fallback (scikit-learn).")
    return EmbeddingBackend(embed=fallback, name="tfidf-fallback", is_fallback=True)


def apply_query_instruction(query: str, backend: EmbeddingBackend) -> str:
    if backend.is_fallback:
        return query
    return f"{BGE_QUERY_INSTRUCTION}{query}"
