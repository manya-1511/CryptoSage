"""
rag/citations.py

Phase 7 -- Citation extraction and formatting for RAG explanations.

Every explanation CryptoSage generates must cite the authoritative
source documents it was actually grounded in -- never a fabricated or
generic reference. This module turns retrieved knowledge-base chunks'
metadata into deduplicated, human-readable citation strings, and keeps
the full retrieved-document record (title, source type, identifier,
similarity score) available for storage/audit.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("cryptosage.rag.citations")

# Source types explicitly supported by the specification. A document
# whose `source_type` metadata isn't one of these is still cited (never
# silently dropped), just logged as an unrecognized type.
SUPPORTED_SOURCE_TYPES: frozenset[str] = frozenset({
    "NIST", "MITRE", "OWASP", "CISA", "RFC", "CVE", "Academic Paper", "Vendor Documentation",
})


@dataclass(frozen=True)
class Citation:
    """One formatted, deduplicated citation."""

    title: str
    source_type: str
    identifier: str
    display: str


def format_citation(metadata: dict[str, Any]) -> Citation:
    """Build a `Citation` from one retrieved chunk's document metadata."""
    title = metadata.get("title") or "Untitled Source"
    source_type = metadata.get("source_type") or "Unknown"
    identifier = metadata.get("identifier") or ""

    if source_type not in SUPPORTED_SOURCE_TYPES:
        logger.debug("Citation source_type '%s' is not in the explicitly supported list.", source_type)

    display = identifier if identifier else title
    return Citation(title=title, source_type=source_type, identifier=identifier, display=display)


def extract_citations(retrieved_documents: list[dict[str, Any]]) -> list[Citation]:
    """Extract the deduplicated set of citations from a list of retrieved documents.

    Args:
        retrieved_documents: Each item is expected to have a `metadata`
            dict (as returned by `rag.retriever.retrieve()`).

    Returns:
        Citations in first-seen order, deduplicated by `identifier`
        (falling back to `title` when no identifier is present).
    """
    seen: set[str] = set()
    citations: list[Citation] = []

    for document in retrieved_documents:
        metadata = document.get("metadata", {})
        citation = format_citation(metadata)
        dedupe_key = citation.identifier or citation.title
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        citations.append(citation)

    logger.info("Extracted %d unique citation(s) from %d retrieved document(s).", len(citations), len(retrieved_documents))
    return citations


def citations_to_reference_strings(citations: list[Citation]) -> list[str]:
    """Format citations as the plain reference strings used in API responses
    (e.g. `["NIST SP 800-57", "OWASP IoT Top 10 (2018)"]`).
    """
    return [citation.display for citation in citations]
