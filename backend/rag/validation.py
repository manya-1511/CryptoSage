"""
rag/validation.py

Phase 7 -- Programmatic validation of LLM-generated explanations.

The prompt (rag/prompt.py) *asks* Qwen not to invent citations, not to
change the algorithm/confidence/risk score/level/factors, and not to
add recommendations -- but a 3B model is not trusted to reliably obey
prompt instructions, so every one of those constraints is re-checked
here, programmatically, against the same structured data the prompt
was built from. This is the "Output Validation" and "Citation
Validation" stages of the pipeline described in the spec:

    Qwen2.5 3B -> Output Validation -> Citation Validation -> result

`validate_explanation()` never crashes and never modifies the LLM's
text -- it only decides pass/fail. On failure, `rag/explain.py` falls
back to the deterministic template rather than trying to "fix" the
LLM's output; per the spec, fallback is preferred over silent repair
for research reliability. The exception is invalid-citation stripping,
which is offered here as an opt-in, clearly-logged alternative but is
NOT the default behavior of `explain_firmware()`.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from rag.citations import Citation, extract_citation_markers, valid_citation_labels

logger = logging.getLogger("cryptosage.rag.validation")

REQUIRED_SECTIONS: tuple[str, ...] = (
    "Algorithm Detection",
    "Confidence Explanation",
    "Risk Assessment Explanation",
    "Recommendation Justification",
    "Referenced Standards",
)

# Minimum non-whitespace length for a section to count as "present" --
# guards against a model emitting an empty/near-empty header with no
# actual explanation under it.
MIN_SECTION_LENGTH = 15


@dataclass
class ValidationResult:
    valid: bool
    missing_sections: list[str] = field(default_factory=list)
    invalid_citations: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "missing_sections": self.missing_sections,
            "invalid_citations": self.invalid_citations,
            "violations": self.violations,
            "reason": self.reason,
        }


def validate_sections(sections: dict[str, str]) -> list[str]:
    """Return the list of required sections that are missing or too short."""
    missing = []
    for name in REQUIRED_SECTIONS:
        content = sections.get(name, "")
        if len(content.strip()) < MIN_SECTION_LENGTH:
            missing.append(name)
    return missing


def validate_citations(sections: dict[str, str], citations: list[Citation]) -> list[str]:
    """Return every citation marker used across `sections` that does not
    correspond to a source actually retrieved for this explanation.
    """
    allowed = valid_citation_labels(citations)
    combined_text = "\n".join(sections.values())
    found = extract_citation_markers(combined_text)
    return [label for label in found if label.strip().lower() not in allowed]


def check_no_upstream_drift(
    sections: dict[str, str],
    algorithm: str,
    confidence: float,
    risk_score: float,
    risk_level: str,
    recommendations: list[str],
    risk_factors: list[dict[str, Any]],
) -> list[str]:
    """Detect obvious violations of "the LLM must not change upstream
    decisions": a different algorithm name asserted as *the* detected
    algorithm, a restated risk score/level/confidence that doesn't
    match, or a recommendation-shaped sentence that isn't one of the
    upstream recommendations.

    This is deliberately narrow rather than a general fact-checker --
    it looks for a small set of well-defined drift patterns rather than
    trying to semantically verify the whole explanation, since a
    false positive here silently discards a correct LLM explanation in
    favor of the (worse-written but always-correct) template fallback.
    """
    violations: list[str] = []
    combined = " ".join(sections.values())
    combined_lower = combined.lower()

    # 1. Risk level drift: the LLM asserting a different one of the
    #    known risk-level words as *the* risk level.
    known_levels = {"low", "medium", "moderate", "high", "critical"}
    risk_section = sections.get("Risk Assessment Explanation", "").lower()
    # Catches "risk level: high", "high risk", and "rated/rating/classified
    # as high" phrasings -- the three common ways a model restates a
    # risk-level word when explaining it.
    asserted_levels = {
        level for level in known_levels
        if re.search(rf"\brisk level[^.]*\b{re.escape(level)}\b", risk_section)
        or re.search(rf"\b{re.escape(level)} risk\b", risk_section)
        or re.search(rf"\b(?:rated|rating|classified|categorized) (?:as )?{re.escape(level)}\b", risk_section)
    }
    if asserted_levels and risk_level.lower() not in asserted_levels:
        violations.append(
            f"Risk Assessment Explanation asserts risk level(s) {sorted(asserted_levels)}, "
            f"which does not match the upstream risk_level '{risk_level}'."
        )

    # 2. Recommendation drift: a "recommend"/"should" sentence in
    #    section 4 that doesn't lexically overlap with any upstream
    #    recommendation likely introduces a new one.
    rec_section = sections.get("Recommendation Justification", "")
    rec_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", rec_section) if s.strip()]
    recommendation_text_lower = " ".join(recommendations).lower()
    for sentence in rec_sentences:
        sentence_lower = sentence.lower()
        looks_prescriptive = bool(re.search(r"\b(recommend|should|must (?:be|upgrade|replace|adopt))\b", sentence_lower))
        if not looks_prescriptive:
            continue
        content_words = {w for w in re.findall(r"[a-z0-9]+", sentence_lower) if len(w) > 4}
        if content_words and not any(w in recommendation_text_lower for w in content_words):
            violations.append(f"Possible unsupported new recommendation: {sentence!r}")

    # 3. New risk factor drift: a factor name mentioned as a cause that
    #    isn't among the upstream-triggered factors. Only checked inside
    #    the Risk Assessment Explanation section itself -- scanning the
    #    whole explanation would also catch legitimate, non-factor
    #    field-name mentions elsewhere (e.g. "stored in the
    #    `risk_factors` evidence" in section 3's own closing sentence,
    #    or `crypto_evidence`/`binary_size` mentioned in section 1/2
    #    while discussing block B features -- neither is a fabricated
    #    risk factor).
    known_factor_names = {str(f.get("factor", "")).lower() for f in risk_factors if f.get("factor")}
    # Schema/field names that legitimately appear in prose and must
    # never be mistaken for a fabricated risk-factor identifier.
    _known_field_names = {
        "risk_factors", "risk_score", "risk_level", "crypto_evidence",
        "known_crypto_library", "binary_size", "instruction_count",
        "section_count", "symbol_count", "algorithm_family",
    }
    if known_factor_names:
        candidate_factors = set(re.findall(r"\b[a-z]+(?:_[a-z]+)+\b", risk_section))
        unknown_factors = candidate_factors - known_factor_names - _known_field_names
        if unknown_factors:
            violations.append(f"Mentions unrecognized risk-factor-like identifier(s): {sorted(unknown_factors)}")

    return violations


def validate_explanation(
    sections: dict[str, str],
    citations: list[Citation],
    algorithm: str,
    confidence: float,
    risk_score: float,
    risk_level: str,
    risk_factors: list[dict[str, Any]],
    recommendations: list[str],
) -> ValidationResult:
    """Run every programmatic check and return one combined verdict.

    A `ValidationResult.valid == False` means `rag/explain.py` should
    discard the LLM output and use `generate_template_explanation()`
    instead -- this function never tries to repair the text itself.
    """
    missing = validate_sections(sections)
    invalid_citations = validate_citations(sections, citations)
    violations = check_no_upstream_drift(
        sections, algorithm, confidence, risk_score, risk_level, recommendations, risk_factors,
    )

    problems = []
    if missing:
        problems.append(f"missing/too-short section(s): {missing}")
    if invalid_citations:
        problems.append(f"invalid citation(s): {invalid_citations}")
    if violations:
        problems.append(f"upstream-drift violation(s): {violations}")

    valid = not problems
    reason = "; ".join(problems) if problems else "all checks passed"

    if not valid:
        logger.warning("LLM output validation FAILED: %s", reason)
    else:
        logger.info("LLM output validation PASSED.")

    return ValidationResult(
        valid=valid,
        missing_sections=missing,
        invalid_citations=invalid_citations,
        violations=violations,
        reason=reason,
    )


def strip_invalid_citations(sections: dict[str, str], invalid_citations: list[str]) -> dict[str, str]:
    """Remove `[LABEL]` markers for every label in `invalid_citations`
    from every section's text, leaving the surrounding sentence intact.

    NOT called automatically by `validate_explanation`/`rag/explain.py`
    -- the spec prefers falling back to the deterministic template over
    silently editing an LLM response for research reliability. This is
    provided only as an explicit, opt-in alternative for callers that
    have decided the tradeoff differently, and every removal is logged.
    """
    cleaned: dict[str, str] = {}
    invalid_set = {label.strip().lower() for label in invalid_citations}
    for name, text in sections.items():
        def _drop(match: re.Match) -> str:
            if match.group(1).strip().lower() in invalid_set:
                logger.info("Stripping invalid citation [%s] from section '%s'.", match.group(1), name)
                return ""
            return match.group(0)

        cleaned[name] = re.sub(r"\[([^\[\]]+)\]", _drop, text)
    return cleaned
