"""
rag/prompt.py

Phase 7 -- Structured prompt construction for the explanation LLM.

Restructured (Phase 7 upgrade) into exactly the three blocks the
upstream/RAG boundary needs:

    A. UPSTREAM DECISIONS       (algorithm, confidence, risk, recs)
    B. OBSERVED BINARY FEATURES (static-analysis evidence)
    C. RETRIEVED EXTERNAL EVIDENCE (knowledge-base chunks)

The previous version repeated the same "do not invent/change X" rule
under nearly every section (~18 numbered rules plus per-section
warnings). That repetition cost prompt tokens without adding grounding
strength for a small model and risked pushing a 3B-parameter model's
effective context past where it reliably follows instructions. The
safety/grounding rules are now stated once, precisely, and referenced
rather than restated -- the constraints themselves are unchanged from
the original prompt; only the wording is condensed.

The LLM is still strictly instructed to explain decisions already
produced by the upstream ML, risk, and recommendation stages, and must
not create new security decisions or infer unsupported relationships
between features and predictions.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("cryptosage.rag.prompt")


SYSTEM_INSTRUCTION = (
    "You are a firmware security analysis assistant. Explain results that "
    "an upstream ML/risk/recommendation pipeline already produced. You do "
    "not make security decisions.\n\n"
    "Rules:\n"
    "1. Never change the algorithm, family, confidence, risk score, risk "
    "level, risk factors, or recommendations shown below.\n"
    "2. Do not treat generic features (entropy, section/symbol count, "
    "binary size, instruction count) as the cause of the ML prediction "
    "unless explicit algorithm-specific evidence (crypto_evidence, matched "
    "constants, symbols, known libraries) is given.\n"
    "3. Cite a claim with the exact bracketed label shown in the Retrieved "
    "Evidence, e.g. [FIPS 197], placed right after the sentence it "
    "supports. Cite only labels that appear there -- never invent a "
    "standard, RFC, CWE, CVE, MITRE, or OWASP identifier.\n"
    "4. If a claim has no supporting retrieved evidence, write: "
    "\"The retrieved evidence does not establish this claim.\" Do not "
    "force a citation onto it.\n"
    "5. Do not use Markdown bold, decorative symbols, or JSON."
)


def _format_feature_summary(feature_vector: dict[str, Any]) -> str:
    """Render selected feature-vector fields (Block B: observed features).

    These are context only -- the LLM must not assume they caused the
    ML prediction unless explicit evidence establishes that link (see
    SYSTEM_INSTRUCTION rule 2).
    """
    keys = (
        "architecture", "binary_size", "entropy", "instruction_count",
        "section_count", "symbol_count", "known_crypto_library",
    )
    lines = [f"- {key}: {feature_vector.get(key)}" for key in keys if key in feature_vector]

    crypto_evidence = feature_vector.get("crypto_evidence")
    if crypto_evidence:
        matched = [name for name, present in crypto_evidence.items() if present]
        lines.append(f"- crypto_evidence matched: {', '.join(matched) if matched else 'none'}")

    return "\n".join(lines) if lines else "(no feature vector fields available)"


def _format_retrieved_context(retrieved_documents: list[dict[str, Any]]) -> str:
    """Render retrieved knowledge-base chunks (Block C) as labeled evidence.

    The label used here is exactly the label SYSTEM_INSTRUCTION rule 3
    requires the model to cite -- `rag/citations.py::valid_citation_labels`
    accepts the same identifier/title fallback used here, so a citation
    the model reproduces from this block is always recognized as valid.
    """
    if not retrieved_documents:
        return "(no supporting documents were retrieved)"

    blocks = []
    for index, document in enumerate(retrieved_documents, start=1):
        metadata = document.get("metadata", {})
        label = metadata.get("identifier") or metadata.get("title") or f"Source {index}"
        content = document.get("content", "")
        similarity = document.get("similarity", "unknown")
        blocks.append(f"[{label}] (similarity={similarity})\n{content}")

    return "\n\n".join(blocks)


def build_explanation_prompt(
    firmware_metadata: dict[str, Any],
    feature_vector: dict[str, Any],
    algorithm: str,
    algorithm_family: str,
    confidence: float,
    risk_score: float,
    risk_level: str,
    risk_factors: list[dict[str, Any]],
    recommendations: list[str],
    retrieved_documents: list[dict[str, Any]],
) -> str:
    """Build the complete structured explanation prompt.

    Separates upstream decisions (A), observed binary features (B),
    and retrieved external evidence (C), so the LLM only ever explains
    already-produced results using only the evidence it was actually
    given -- it never decides the classification, risk, or
    recommendations itself.
    """
    risk_factor_lines = "\n".join(
        f"- {f.get('factor')} (weight={f.get('weight')}, contribution={f.get('contribution')})"
        for f in risk_factors
    ) or "(no risk factors triggered)"

    recommendation_lines = "\n".join(f"- {r}" for r in recommendations) or "(no recommendations)"

    prompt = f"""{SYSTEM_INSTRUCTION}

=== A. UPSTREAM DECISIONS (already produced -- do not change) ===
algorithm: {algorithm}
algorithm_family: {algorithm_family}
confidence: {confidence}%
risk_score: {risk_score}
risk_level: {risk_level}
risk_factors:
{risk_factor_lines}
recommendations:
{recommendation_lines}

=== B. OBSERVED BINARY FEATURES (context only, see rule 2) ===
{_format_feature_summary(feature_vector)}

=== C. RETRIEVED EXTERNAL EVIDENCE (the only sources you may cite) ===
{_format_retrieved_context(retrieved_documents)}

=== TASK ===
Firmware file: {firmware_metadata.get("filename", "unknown")}

Write exactly these five numbered sections, nothing before section 1 or
after section 5. Cite evidence from block C next to the specific claim
it supports (rule 3), not only in section 5.

1. Algorithm Detection -- explain the algorithm/family from block A,
   using block B's crypto-specific evidence if present (rule 2).
2. Confidence Explanation -- explain what the confidence in block A
   means; do not attribute it to specific features unless block B
   states that link explicitly.
3. Risk Assessment Explanation -- explain risk_score/risk_level using
   only the risk_factors listed in block A.
4. Recommendation Justification -- justify each recommendation in
   block A using block A's risk factors and block C's evidence.
5. Referenced Standards -- list only the block-C labels you actually
   cited above, deduplicated.
"""

    logger.debug(
        "Prompt constructed: %d characters, %d retrieved document(s).",
        len(prompt), len(retrieved_documents),
    )
    return prompt
