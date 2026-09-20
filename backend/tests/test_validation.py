from __future__ import annotations

from rag.citations import format_citation
from rag.validation import validate_explanation, validate_sections, strip_invalid_citations

CITATIONS = [format_citation({"identifier": "FIPS 197", "title": "AES", "source_type": "NIST"})]

BASE_SECTIONS = {
    "Algorithm Detection": "AES was detected based on matched constants [FIPS 197].",
    "Confidence Explanation": "The classifier reported 87.5 percent confidence for this prediction.",
    "Risk Assessment Explanation": "Risk score is 42.0, rated medium, due to weak_key_length [FIPS 197].",
    "Recommendation Justification": "Upgrading key management addresses weak_key_length.",
    "Referenced Standards": "The explanation above cites FIPS 197 as its supporting source.",
}

RISK_FACTORS = [{"factor": "weak_key_length", "weight": 0.4, "contribution": 12.0}]
RECOMMENDATIONS = ["Upgrade key management practices"]


def _validate(sections):
    return validate_explanation(
        sections, CITATIONS,
        algorithm="AES", confidence=87.5, risk_score=42.0, risk_level="medium",
        risk_factors=RISK_FACTORS, recommendations=RECOMMENDATIONS,
    )


def test_valid_explanation_passes():
    result = _validate(BASE_SECTIONS)
    assert result.valid is True


def test_rejects_missing_section():
    sections = dict(BASE_SECTIONS)
    del sections["Referenced Standards"]
    result = _validate(sections)
    assert result.valid is False
    assert "Referenced Standards" in result.missing_sections


def test_rejects_too_short_section():
    sections = dict(BASE_SECTIONS)
    sections["Confidence Explanation"] = "ok."
    result = _validate(sections)
    assert result.valid is False


def test_rejects_unsupported_citation():
    sections = dict(BASE_SECTIONS)
    sections["Algorithm Detection"] = "AES was detected [RFC_9999_MADE_UP]."
    result = _validate(sections)
    assert result.valid is False
    assert "RFC_9999_MADE_UP" in result.invalid_citations


def test_rejects_changed_risk_level():
    sections = dict(BASE_SECTIONS)
    sections["Risk Assessment Explanation"] = "Risk score is 42.0, rated critical, due to weak_key_length [FIPS 197]."
    result = _validate(sections)
    assert result.valid is False
    assert any("critical" in v for v in result.violations)


def test_rejects_new_recommendation():
    sections = dict(BASE_SECTIONS)
    sections["Recommendation Justification"] = (
        "You should immediately replace the entire firmware image and disable network access."
    )
    result = _validate(sections)
    assert result.valid is False
    assert any("unsupported new recommendation" in v for v in result.violations)


def test_matching_recommendation_wording_is_not_flagged():
    sections = dict(BASE_SECTIONS)
    sections["Recommendation Justification"] = (
        "It is recommended to upgrade key management practices to address weak_key_length."
    )
    result = _validate(sections)
    assert result.valid is True


def test_benign_field_name_mentions_are_not_flagged_as_new_risk_factors():
    sections = dict(BASE_SECTIONS)
    sections["Risk Assessment Explanation"] = (
        "Risk score is 42.0, rated medium. Contribution weights are stored in risk_factors evidence [FIPS 197]."
    )
    result = _validate(sections)
    assert result.valid is True


def test_validate_sections_reports_all_five_when_totally_empty():
    missing = validate_sections({})
    assert len(missing) == 5


def test_strip_invalid_citations_removes_only_flagged_labels():
    sections = {"Algorithm Detection": "AES detected [FIPS 197] and [MADE_UP]."}
    cleaned = strip_invalid_citations(sections, ["MADE_UP"])
    assert "[FIPS 197]" in cleaned["Algorithm Detection"]
    assert "[MADE_UP]" not in cleaned["Algorithm Detection"]
