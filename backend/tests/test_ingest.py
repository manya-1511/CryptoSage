from __future__ import annotations

from rag.ingest import chunk_document, discover_documents, ingest_knowledge_base, parse_document, split_into_sections


def test_discover_documents_empty_dir_returns_empty_list(tmp_path):
    missing = tmp_path / "does_not_exist"
    assert discover_documents(missing) == []


def test_parse_document_reads_front_matter(knowledge_base_dir):
    parsed = parse_document(knowledge_base_dir / "fips197.md")
    assert parsed["identifier"] == "FIPS 197"
    assert parsed["source_type"] == "NIST"
    assert "AES" in parsed["content"]


def test_split_into_sections_keeps_heading_with_its_body():
    content = "# Title\n\n## Overview\n\nAES is great.\n\n## Security\n\nAES is secure.\n"
    sections = split_into_sections(content)
    titles = [s["section"] for s in sections]
    assert "Overview" in titles
    assert "Security" in titles
    overview = next(s for s in sections if s["section"] == "Overview")
    assert "AES is great" in overview["text"]


def test_split_into_sections_no_headings_returns_single_block():
    sections = split_into_sections("Just plain text with no headings at all.")
    assert len(sections) == 1
    assert sections[0]["section"] == ""


def test_chunk_document_returns_section_tagged_chunks(knowledge_base_dir):
    parsed = parse_document(knowledge_base_dir / "fips197.md")
    chunks = chunk_document(parsed["content"])
    assert len(chunks) > 0
    assert all("section" in c and "text" in c for c in chunks)


def test_ingest_knowledge_base_adds_section_and_document_category_metadata(knowledge_base_dir, tmp_path):
    from config import get_settings

    persist_dir = tmp_path / "chroma"
    summary = ingest_knowledge_base(knowledge_base_dir=knowledge_base_dir, persist_dir=persist_dir)
    assert summary["documents"] == 3
    assert summary["chunks"] > 0

    import chromadb

    client = chromadb.PersistentClient(path=str(persist_dir))
    collection = client.get_collection(get_settings().RAG_COLLECTION_NAME, embedding_function=None)
    got = collection.get(where={"source_file": "fips197.md"})
    assert got["metadatas"], "expected at least one chunk from fips197.md"
    metadata = got["metadatas"][0]
    assert "section" in metadata
    assert "document_category" in metadata
    assert metadata["document_category"] == "standard"  # NIST -> "standard"
    # Original fields must still be present (backward compatibility).
    for field in ("title", "source_type", "identifier", "source_file", "chunk_index"):
        assert field in metadata

    # A MITRE-sourced document maps to a different category, confirming
    # the mapping isn't just a constant.
    mitre_chunk = collection.get(where={"source_file": "cwe327.md"})
    assert mitre_chunk["metadatas"][0]["document_category"] == "weakness_taxonomy"


def test_ingest_empty_knowledge_base_does_not_crash(tmp_path):
    empty_kb = tmp_path / "empty_kb"
    empty_kb.mkdir()
    summary = ingest_knowledge_base(knowledge_base_dir=empty_kb, persist_dir=tmp_path / "chroma2")
    assert summary["documents"] == 0
    assert summary["chunks"] == 0


def test_ingest_is_idempotent_and_rebuilds_cleanly(knowledge_base_dir, tmp_path):
    persist_dir = tmp_path / "chroma3"
    first = ingest_knowledge_base(knowledge_base_dir=knowledge_base_dir, persist_dir=persist_dir)
    second = ingest_knowledge_base(knowledge_base_dir=knowledge_base_dir, persist_dir=persist_dir)
    assert first["chunks"] == second["chunks"]
