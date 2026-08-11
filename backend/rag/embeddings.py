"""
rag/embeddings.py

Phase 7 -- Embedding generation for the RAG knowledge base.

The specified embedding model is `BAAI/bge-small-en-v1.5` via
`sentence-transformers`. This module tries to load exactly that model
first. If it cannot be downloaded or loaded (e.g. no network access to
the Hugging Face Hub in a given deployment), it falls back to a local,
dependency-light TF-IDF embedding function built with scikit-learn, so
ingestion and retrieval remain fully functional rather than failing
outright -- the fallback is always logged clearly and reported in
`EmbeddingBackend.name`, never silently substituted.

Both paths implement ChromaDB's `EmbeddingFunction` protocol
(`__call__(input: list[str]) -> list[list[float]]`), so `rag/retriever.py`
never needs to know which backend is active.
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
# bge models are instruction-tuned to expect this prefix on retrieval
# queries (not on the documents being indexed) for best results.
BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


@dataclass
class EmbeddingBackend:
    """A ready-to-use embedding function plus which backend produced it."""

    embed: Any  # callable: list[str] -> list[list[float]]
    name: str
    is_fallback: bool


class SentenceTransformerEmbeddingFunction(EmbeddingFunction):
    """ChromaDB-compatible embedding function wrapping sentence-transformers."""

    def __init__(self, model: Any) -> None:
        self._model = model

    def __call__(self, input: Documents) -> Embeddings:  # noqa: A002 - ChromaDB's required param name
        embeddings = self._model.encode(list(input), normalize_embeddings=True)
        return [vector.tolist() for vector in embeddings]

    def name(self) -> str:
        return BGE_MODEL_NAME


class TfidfEmbeddingFunction(EmbeddingFunction):
    """A local, dependency-light fallback embedding function (scikit-learn TF-IDF).

    Used only when the configured sentence-transformers model can't be
    loaded. Fit on the knowledge base's chunks during ingestion and
    **persisted to disk** (`vectorizer_path`), since ingestion and
    retrieval normally run in separate processes (a batch ingestion job
    vs. a long-running API server) -- without persistence, a freshly
    constructed vectorizer in the retrieval process would have no
    fitted vocabulary to embed queries against. This is a materially
    weaker semantic representation than a trained embedding model, but
    it keeps ChromaDB similarity search fully operational end-to-end
    without any network dependency.
    """

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


def _try_load_sentence_transformer(model_name: str, timeout_seconds: int = 15) -> Optional[Any]:
    """Attempt to load the configured sentence-transformers model.

    Runs the load in a background daemon thread with a hard wall-clock
    timeout. This is necessary because, in a deployment where the
    Hugging Face Hub domain is network-blocked (rather than actively
    refusing connections), the underlying HTTP client can hang well
    past any request-level timeout it's configured with -- a plain
    `socket.setdefaulttimeout()` is not sufficient, since
    `huggingface_hub`'s client does not consistently honor it. A thread
    with `join(timeout=...)` guarantees this function itself never
    blocks longer than `timeout_seconds`, even if the network call
    never completes; the orphaned thread is a daemon thread, so it
    cannot prevent process exit and is abandoned once we time out.

    Returns None (never raises, never hangs past the timeout) if the
    package isn't installed or the model can't be downloaded/loaded in
    time -- both are treated as "fall back to TF-IDF", logged clearly.
    """
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
    """Return the best available embedding backend.

    Tries `model_name` via sentence-transformers first; falls back to
    TF-IDF (scikit-learn) if that model can't be loaded. Always
    returns a usable backend -- never raises.

    Args:
        model_name: The sentence-transformers model to try first.
        tfidf_persist_path: Where the TF-IDF fallback's fitted
            vectorizer is persisted/loaded from, so retrieval (a
            separate process from ingestion) can reuse the vocabulary
            fitted during ingestion. Defaults to a path alongside the
            configured ChromaDB store.
    """
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
    """Apply the bge query-instruction prefix, only when the real bge model is active.

    The TF-IDF fallback has no notion of instruction-tuning, so the
    prefix would just add noise there and is skipped.
    """
    if backend.is_fallback:
        return query
    return f"{BGE_QUERY_INSTRUCTION}{query}"
