"""
rag/ingest.py

Phase 7 -- Knowledge base ingestion: discover documents, chunk them,
generate embeddings, and store them in ChromaDB.

Supports the document categories named in the specification (NIST
Publications, MITRE CWE/ATT&CK, OWASP IoT Top 10, CISA Advisories, RFC
Documents, Cryptographic Standards, Academic Papers, Vendor
Documentation) via a lightweight, per-file YAML-style front-matter
header (`title`, `source_type`, `identifier`) at the top of each
Markdown/text file in `rag/knowledge_base/`. Chunking uses LangChain's
`RecursiveCharacterTextSplitter`.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import get_settings
from rag.embeddings import EmbeddingBackend, get_embedding_backend

logger = logging.getLogger("cryptosage.rag.ingest")

settings = get_settings()

# Front-matter delimiter, e.g.:
#   ---
#   title: NIST FIPS 197 — Advanced Encryption Standard (AES)
#   source_type: NIST
#   identifier: FIPS 197
#   ---
_FRONT_MATTER_RE = re.compile(r"^---\n(?P<header>.*?)\n---\n(?P<body>.*)$", re.DOTALL)

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".md", ".txt"})


def discover_documents(knowledge_base_dir: Path) -> list[Path]:
    """Find every ingestible document under `knowledge_base_dir`.

    Never raises: a missing directory simply yields no documents
    (logged as a warning), consistent with graceful-recovery error
    handling elsewhere in the pipeline.
    """
    if not knowledge_base_dir.exists():
        logger.warning("Knowledge base directory does not exist: %s", knowledge_base_dir)
        return []

    documents = sorted(
        path for path in knowledge_base_dir.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )
    logger.info("Discovered %d knowledge base document(s) under %s", len(documents), knowledge_base_dir)
    return documents


def parse_document(path: Path) -> dict[str, Any]:
    """Parse one document's front-matter metadata and body content.

    A document with no front-matter is still ingested (with a
    best-effort `title` derived from the filename), rather than being
    skipped -- partial metadata is preferred over silently dropping
    content from the knowledge base.
    """
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.error("Could not read knowledge base document %s: %s", path, exc)
        return {"title": path.stem, "source_type": "Unknown", "identifier": "", "content": ""}

    match = _FRONT_MATTER_RE.match(raw_text)
    if not match:
        logger.debug("No front-matter found in %s; using filename as title.", path.name)
        return {"title": path.stem.replace("_", " ").title(), "source_type": "Unknown", "identifier": "", "content": raw_text.strip()}

    metadata: dict[str, str] = {}
    for line in match.group("header").splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            metadata[key.strip()] = value.strip()

    return {
        "title": metadata.get("title", path.stem),
        "source_type": metadata.get("source_type", "Unknown"),
        "identifier": metadata.get("identifier", ""),
        "content": match.group("body").strip(),
    }


def chunk_document(content: str, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split a document's body text into overlapping chunks (LangChain).

    `RecursiveCharacterTextSplitter` tries paragraph, then sentence,
    then word boundaries in order, so chunks stay coherent rather than
    breaking mid-sentence wherever possible.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_text(content)


def ingest_knowledge_base(
    knowledge_base_dir: Path | None = None,
    persist_dir: Path | None = None,
    embedding_backend: EmbeddingBackend | None = None,
) -> dict[str, Any]:
    """Ingest every document in the knowledge base into ChromaDB.

    Idempotent: re-running clears and rebuilds the collection, so
    ingestion can safely be re-run after the knowledge base is edited
    without accumulating duplicate/stale chunks.

    Returns a summary dict: `{"documents": N, "chunks": M, "embedding_backend": name}`.
    """
    import chromadb

    knowledge_base_dir = knowledge_base_dir or settings.RAG_KNOWLEDGE_BASE_DIR
    persist_dir = persist_dir or settings.RAG_CHROMA_PERSIST_DIR
    embedding_backend = embedding_backend or get_embedding_backend()

    logger.info("Knowledge base loading started: %s", knowledge_base_dir)
    documents = discover_documents(knowledge_base_dir)
    if not documents:
        logger.warning("No knowledge base documents found; ingestion produced an empty collection.")

    persist_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(persist_dir))

    try:
        client.delete_collection(settings.RAG_COLLECTION_NAME)
    except Exception:  # noqa: BLE001 - collection may not exist yet on first run
        pass

    collection = client.create_collection(
        name=settings.RAG_COLLECTION_NAME,
        embedding_function=embedding_backend.embed,
        metadata={"embedding_backend": embedding_backend.name},
    )

    all_chunk_texts: list[str] = []
    all_chunk_ids: list[str] = []
    all_chunk_metadata: list[dict[str, Any]] = []

    for document_path in documents:
        parsed = parse_document(document_path)
        if not parsed["content"]:
            logger.warning("Skipping empty document: %s", document_path.name)
            continue

        chunks = chunk_document(parsed["content"])
        logger.info("Chunked '%s' into %d chunk(s).", parsed["title"], len(chunks))

        for chunk_index, chunk_text in enumerate(chunks):
            all_chunk_texts.append(chunk_text)
            all_chunk_ids.append(f"{document_path.stem}::{chunk_index}")
            all_chunk_metadata.append({
                "title": parsed["title"],
                "source_type": parsed["source_type"],
                "identifier": parsed["identifier"],
                "source_file": document_path.name,
                "chunk_index": chunk_index,
            })

    if all_chunk_texts:
        logger.info("Embedding generation started for %d chunk(s) (backend=%s)...", len(all_chunk_texts), embedding_backend.name)
        collection.add(documents=all_chunk_texts, ids=all_chunk_ids, metadatas=all_chunk_metadata)
        logger.info("Embedding generation completed; %d chunk(s) stored in ChromaDB.", len(all_chunk_texts))

    summary = {
        "documents": len(documents),
        "chunks": len(all_chunk_texts),
        "embedding_backend": embedding_backend.name,
    }
    logger.info("Knowledge base ingestion completed: %s", summary)
    return summary
