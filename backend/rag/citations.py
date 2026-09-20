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
import re
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


# ============================================================
# SENTENCE/CLAIM-LEVEL CITATION VALIDATION
# ============================================================
#
# Used both by rag/validation.py (to reject an LLM response that cites
# something never retrieved) and by evaluation. `[LABEL]` markers found
# in generated text are matched only against citations actually built
# from *retrieved* metadata -- an LLM cannot make up a label and have
# it pass.

_CITATION_MARKER_RE = re.compile(r"\[([^\[\]]+)\]")


def extract_citation_markers(text: str) -> list[str]:
    """Pull every `[LABEL]`-style marker out of generated text, in
    first-seen order, deduplicated. Does not judge validity -- see
    `validate_citation_markers`.
    """
    if not text:
        return []
    return list(dict.fromkeys(_CITATION_MARKER_RE.findall(text)))


def valid_citation_labels(citations: list[Citation]) -> set[str]:
    """The set of labels an LLM/template is allowed to cite: each
    citation's `display` value (what actually appears as `[LABEL]` in
    prompts/output) plus its raw identifier and title as fallbacks, so
    a citation is accepted whichever of those the model reproduces.
    """
    labels: set[str] = set()
    for citation in citations:
        for value in (citation.display, citation.identifier, citation.title):
            if value:
                labels.add(value.strip().lower())
    return labels


def validate_citation_markers(text: str, citations: list[Citation]) -> dict[str, Any]:
    """Check every `[LABEL]` marker in `text` against `citations`
    (built from the documents actually retrieved for this explanation).

    Returns:
        {
            "valid": bool,               # True iff every marker matched
            "cited_labels": [...],       # markers found in `text`
            "invalid_labels": [...],     # markers with no matching retrieved source
            "allowed_labels": [...],     # labels that WOULD have been valid
        }
    """
    allowed = valid_citation_labels(citations)
    found = extract_citation_markers(text)
    invalid = [label for label in found if label.strip().lower() not in allowed]

    if invalid:
        logger.warning("Invalid citation(s) detected: %s. Allowed sources: %s", invalid, sorted(allowed))

    return {
        "valid": not invalid,
        "cited_labels": found,
        "invalid_labels": invalid,
        "allowed_labels": sorted(allowed),
    }


def sentence_level_citations(text: str, citations: list[Citation]) -> list[dict[str, Any]]:
    """Split `text` into sentences and report which retrieved citation(s)
    (if any) each sentence cites, for sentence/claim-level citation
    display and for the "citation completeness" evaluation metric
    (does every factual-looking claim carry a citation?).

    A sentence with no `[LABEL]` marker at all is reported with
    `has_citation=False` and `unsupported=True` only when it does not
    already contain the deterministic "does not establish" disclaimer
    the prompt requires for unsupported claims -- such a sentence is
    intentionally uncited, not missing a citation it should have had.
    """
    if not text:
        return []

    allowed = valid_citation_labels(citations)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]

    results = []
    for sentence in sentences:
        markers = extract_citation_markers(sentence)
        matched = [m for m in markers if m.strip().lower() in allowed]
        unmatched = [m for m in markers if m.strip().lower() not in allowed]
        disclaims = "does not establish" in sentence.lower()
        results.append({
            "sentence": sentence,
            "has_citation": bool(matched),
            "cited_labels": matched,
            "invalid_labels": unmatched,
            "unsupported_disclaimer": disclaims,
        })
    return results
