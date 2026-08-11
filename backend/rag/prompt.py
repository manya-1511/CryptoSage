"""
rag/prompt.py

Phase 7 -- Structured prompt construction for the explanation LLM.

Builds a single, structured prompt containing everything the LLM needs
to produce an evidence-backed explanation -- firmware metadata, binary
features, the detected algorithm and confidence, risk factors and
recommendations, and the retrieved knowledge-base context -- with an
explicit instruction to explain, cite evidence, reference sources, and
never hallucinate beyond the provided context.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("cryptosage.rag.prompt")

SYSTEM_INSTRUCTION = (
    "You are a firmware security analysis assistant. You explain, in plain "
    "language, the results a static-analysis and machine-learning pipeline "
    "has already produced. You do not make new security decisions, you do "
    "not change the algorithm identification, risk score, or "
    "recommendations -- you only explain and justify them using the "
    "provided context. Cite only the retrieved reference documents given "
    "to you; never invent a standard, RFC, or CVE number that was not "
    "provided. If the retrieved context does not fully support a claim, "
    "say so rather than filling the gap with an unsupported assertion."
)


def _format_feature_summary(feature_vector: dict[str, Any]) -> str:
    """Render the handful of feature-vector fields most relevant to an
    explanation (not the full raw vector, to keep the prompt focused).
    """
    keys = (
        "architecture", "binary_size", "entropy", "instruction_count",
        "section_count", "symbol_count", "known_crypto_library",
    )
    lines = [f"- {key}: {feature_vector.get(key)}" for key in keys if key in feature_vector]
    crypto_evidence = feature_vector.get("crypto_evidence")
    if crypto_evidence:
        matched = [name for name, present in crypto_evidence.items() if present]
        if matched:
            lines.append(f"- crypto_evidence matched: {', '.join(matched)}")
    return "\n".join(lines) if lines else "(no feature vector fields available)"


def _format_retrieved_context(retrieved_documents: list[dict[str, Any]]) -> str:
    """Render retrieved knowledge-base chunks as labeled, citable context blocks."""
    if not retrieved_documents:
        return "(no supporting documents were retrieved)"

    blocks = []
    for index, document in enumerate(retrieved_documents, start=1):
        metadata = document.get("metadata", {})
        label = metadata.get("identifier") or metadata.get("title") or f"Source {index}"
        blocks.append(f"[{label}]\n{document.get('content', '')}")
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
    """Build the full structured prompt for the explanation LLM.

    Returns a single prompt string containing the system instruction,
    every structured input, and the retrieved context, ending with an
    explicit request for the five required explanation sections.
    """
    risk_factor_lines = "\n".join(
        f"- {factor.get('factor')}: weight={factor.get('weight')}, contribution={factor.get('contribution')}"
        for factor in risk_factors
    ) or "(no risk factors triggered)"

    recommendation_lines = "\n".join(f"- {rec}" for rec in recommendations) or "(no recommendations)"

    prompt = f"""{SYSTEM_INSTRUCTION}

## Firmware Metadata
- filename: {firmware_metadata.get('filename', 'unknown')}
- file_hash: {firmware_metadata.get('file_hash', 'unknown')}
- upload_time: {firmware_metadata.get('upload_time', 'unknown')}

## Binary Features (summary)
{_format_feature_summary(feature_vector)}

## Detected Algorithm
- family: {algorithm_family}
- algorithm: {algorithm}
- confidence: {confidence}%

## Risk Assessment
- risk_score: {risk_score}
- risk_level: {risk_level}
- triggered risk factors:
{risk_factor_lines}

## Recommendations
{recommendation_lines}

## Retrieved Reference Context
{_format_retrieved_context(retrieved_documents)}

## Task
Using ONLY the information above, write a structured explanation with
exactly these five sections:

1. Algorithm Detection -- why this specific algorithm/family was
   identified, referencing the matched evidence (crypto constants,
   symbols, or other feature-vector signals).
2. Confidence Explanation -- what the {confidence}% confidence score
   means and what it depends on.
3. Risk Assessment Explanation -- why the firmware received a
   risk_score of {risk_score} ({risk_level}), referencing the specific
   triggered risk factors above.
4. Recommendation Justification -- why each recommendation was made,
   tied to the risk factor(s) that triggered it.
5. Referenced Standards -- list the specific retrieved sources (by the
   [label] shown above) that support the explanation. Do not cite any
   source not shown in the Retrieved Reference Context.

Do not introduce any fact, standard, or number not present above."""

    logger.debug("Prompt constructed: %d characters, %d retrieved document(s).", len(prompt), len(retrieved_documents))
    return prompt
