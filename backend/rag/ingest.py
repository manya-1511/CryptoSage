"""
rag/ingest.py

Phase 7 -- Knowledge base ingestion: discover documents, chunk them,
generate embeddings, and store them in ChromaDB.
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

_FRONT_MATTER_RE = re.compile(r"^---\n(?P<header>.*?)\n---\n(?P<body>.*)$", re.DOTALL)

# Matches a Markdown heading line ("#", "##", ... "######") so a
# document's body can be split into (section_title, section_body)
# pairs *before* the character-level splitter runs on each section.
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)

# Optional "document_category" front-matter field maps a source_type
# onto the broader groupings named in the spec, for filtering/reporting.
_SOURCE_TYPE_TO_CATEGORY: dict[str, str] = {
    "NIST": "standard",
    "RFC": "standard",
    "Cryptographic Standard": "standard",
    "MITRE": "weakness_taxonomy",
    "CWE": "weakness_taxonomy",
    "ATT&CK": "threat_taxonomy",
    "OWASP": "guideline",
    "CISA": "advisory",
    "Academic Paper": "research",
    "Vendor Documentation": "vendor",
}

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".md", ".txt"})
# ChromaDB distance metric for the collection. Must match
# rag/retriever.py::CHROMA_DISTANCE_METRIC -- ingestion and retrieval
# must agree on what "distance" means, or `1 - distance` in the
# retriever is not a meaningful similarity.
CHROMA_DISTANCE_METRIC = "cosine"


def discover_documents(knowledge_base_dir: Path) -> list[Path]:
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


def split_into_sections(content: str) -> list[dict[str, str]]:
    """Split a document body into `{"section": heading, "text": body}` blocks
    on Markdown headings (`#`..`######`), so a section's heading stays
    attached to its own paragraphs before the character-level splitter
    ever runs. Content preceding the first heading (or a document with
    no headings at all) becomes a single section with `section=""`.
    """
    headings = list(_HEADING_RE.finditer(content))
    if not headings:
        return [{"section": "", "text": content}]

    sections: list[dict[str, str]] = []
    if headings[0].start() > 0:
        preamble = content[: headings[0].start()].strip()
        if preamble:
            sections.append({"section": "", "text": preamble})

    for i, match in enumerate(headings):
        title = match.group(2).strip()
        start = match.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(content)
        body = content[start:end].strip()
        sections.append({"section": title, "text": f"{title}\n{body}" if body else title})

    return sections


def chunk_document(content: str, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP) -> list[dict[str, str]]:
    """Split a document's body text into overlapping chunks, keeping
    headings attached to their own paragraphs where possible.

    Two passes:
      1. `split_into_sections` groups the body under its Markdown
         headings (if any), so a heading and the paragraphs under it
         are never separated by an arbitrary character-count cut.
      2. Within each section, LangChain's `RecursiveCharacterTextSplitter`
         (paragraph, then sentence, then word boundaries, in order)
         further splits only if that section alone still exceeds
         `chunk_size` -- most knowledge-base sections (NIST/CWE/OWASP
         entries etc.) are short enough that this second pass is a
         no-op and the section is kept whole.

    Returns `{"section": heading, "text": chunk_text}` dicts, not bare
    strings, so callers can attach "section" to each chunk's metadata.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks: list[dict[str, str]] = []
    for block in split_into_sections(content):
        section_title, text = block["section"], block["text"]
        if not text:
            continue
        for piece in splitter.split_text(text):
            chunks.append({"section": section_title, "text": piece})
    return chunks


def ingest_knowledge_base(
    knowledge_base_dir: Path | None = None,
    persist_dir: Path | None = None,
    embedding_backend: EmbeddingBackend | None = None,
) -> dict[str, Any]:
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
    except Exception:  # noqa: BLE001
        pass

    collection = client.create_collection(
        name=settings.RAG_COLLECTION_NAME,
        embedding_function=embedding_backend.embed,
        # Explicit distance metric -- see CHROMA_DISTANCE_METRIC above
        # and rag/retriever.py's module docstring. Without this,
        # ChromaDB's default (also cosine, but implicit) could silently
        # diverge from what the retriever assumes when converting
        # `distance` to `similarity`.
        metadata={"embedding_backend": embedding_backend.name, "hnsw:space": CHROMA_DISTANCE_METRIC},
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
        logger.info("Chunked '%s' into %d chunk(s) (document-structure-aware).", parsed["title"], len(chunks))

        document_category = _SOURCE_TYPE_TO_CATEGORY.get(parsed["source_type"], "other")

        for chunk_index, chunk in enumerate(chunks):
            all_chunk_texts.append(chunk["text"])
            all_chunk_ids.append(f"{document_path.stem}::{chunk_index}")
            # Original metadata fields are unchanged (title, source_type,
            # identifier, source_file, chunk_index) -- "section" and
            # "document_category" are additive, so existing consumers of
            # this metadata keep working unmodified.
            all_chunk_metadata.append({
                "title": parsed["title"],
                "source_type": parsed["source_type"],
                "identifier": parsed["identifier"],
                "source_file": document_path.name,
                "chunk_index": chunk_index,
                "section": chunk["section"],
                "document_category": document_category,
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
