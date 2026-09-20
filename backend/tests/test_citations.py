from __future__ import annotations

from rag.citations import (
    extract_citation_markers,
    extract_citations,
    format_citation,
    sentence_level_citations,
    validate_citation_markers,
    valid_citation_labels,
)


def _doc(identifier="", title="", source_type="NIST"):
    return {"metadata": {"identifier": identifier, "title": title, "source_type": source_type}}


def test_dedupes_citations_by_identifier():
    docs = [
        _doc(identifier="FIPS 197", title="AES"),
        _doc(identifier="FIPS 197", title="AES (duplicate chunk)"),
        _doc(identifier="CWE-327", title="Broken crypto"),
    ]
    citations = extract_citations(docs)
    assert len(citations) == 2
    assert [c.identifier for c in citations] == ["FIPS 197", "CWE-327"]


def test_missing_identifier_falls_back_to_title_for_dedupe():
    docs = [_doc(identifier="", title="Untitled Vendor Doc"), _doc(identifier="", title="Untitled Vendor Doc")]
    citations = extract_citations(docs)
    assert len(citations) == 1
    assert citations[0].display == "Untitled Vendor Doc"


def test_unknown_source_type_is_still_cited_not_dropped():
    docs = [_doc(identifier="X-1", source_type="SomeRandomVendorBlog")]
    citations = extract_citations(docs)
    assert len(citations) == 1
    assert citations[0].source_type == "SomeRandomVendorBlog"


def test_format_citation_prefers_identifier_over_title_for_display():
    citation = format_citation({"identifier": "FIPS 197", "title": "Advanced Encryption Standard", "source_type": "NIST"})
    assert citation.display == "FIPS 197"


def test_valid_citation_marker_passes_validation():
    docs = [_doc(identifier="FIPS 197")]
    citations = extract_citations(docs)
    result = validate_citation_markers("AES is secure [FIPS 197].", citations)
    assert result["valid"] is True
    assert result["invalid_labels"] == []


def test_invalid_citation_marker_fails_validation():
    docs = [_doc(identifier="FIPS 197")]
    citations = extract_citations(docs)
    result = validate_citation_markers("AES is secure [MADE_UP_RFC_9999].", citations)
    assert result["valid"] is False
    assert result["invalid_labels"] == ["MADE_UP_RFC_9999"]


def test_extract_citation_markers_dedupes_and_preserves_order():
    markers = extract_citation_markers("[A] then [B] then [A] again")
    assert markers == ["A", "B"]


def test_sentence_level_citations_flags_uncited_factual_sentences():
    docs = [_doc(identifier="FIPS 197")]
    citations = extract_citations(docs)
    text = "AES is a block cipher defined by NIST [FIPS 197]. It uses a 128-bit block size."
    results = sentence_level_citations(text, citations)
    assert results[0]["has_citation"] is True
    assert results[1]["has_citation"] is False


def test_sentence_level_citations_respects_unsupported_disclaimer():
    docs = [_doc(identifier="FIPS 197")]
    citations = extract_citations(docs)
    text = "The retrieved evidence does not establish this claim."
    results = sentence_level_citations(text, citations)
    assert results[0]["unsupported_disclaimer"] is True
