"""
rag/prompt.py

Phase 7 -- Structured prompt construction for the explanation LLM.

Builds a structured prompt containing:
- firmware metadata
- selected binary features
- detected algorithm and family
- ML confidence
- risk assessment
- triggered risk factors
- recommendations
- retrieved knowledge-base evidence

The LLM is strictly instructed to explain decisions already produced by
the upstream ML, risk, and recommendation stages. It must not create new
security decisions or infer unsupported relationships between features
and predictions.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("cryptosage.rag.prompt")


SYSTEM_INSTRUCTION = (
    "You are a firmware security analysis assistant. "
    "Your task is to explain the results already produced by an upstream "
    "static-analysis, machine-learning, risk-assessment, and recommendation "
    "pipeline.\n\n"

    "You MUST NOT make new security decisions. "
    "You MUST NOT change the detected algorithm, algorithm family, "
    "confidence score, risk score, risk level, risk factors, or "
    "recommendations.\n\n"

    "Use only the information explicitly provided in this prompt. "
    "Do not invent missing evidence, feature importance, model behavior, "
    "security properties, standards, RFC numbers, CVEs, or recommendations.\n\n"

    "For algorithm detection, distinguish between the classification result "
    "and the evidence supplied to explain that result. If explicit "
    "algorithm-specific evidence such as crypto_evidence, matched constants, "
    "symbols, known cryptographic libraries, or other direct indicators is "
    "not provided, do not infer that generic features caused the prediction. "
    "Instead, clearly state that the classification was produced by the "
    "upstream ML pipeline and that the available context does not provide "
    "the specific feature-level basis for the classification.\n\n"

    "Do not claim that entropy, section count, symbol count, binary size, "
    "instruction count, or other generic binary features caused or increased "
    "the confidence of a particular algorithm unless the prompt explicitly "
    "provides that relationship.\n\n"

    "For risk explanations, use only the explicitly supplied risk factors "
    "and their contributions. Do not invent weights or causes when they are "
    "missing.\n\n"

    "For recommendations, justify each recommendation only using the "
    "provided risk factors and retrieved reference context.\n\n"

    "Cite only retrieved reference documents that are explicitly provided "
    "in the Retrieved Reference Context. Never invent or introduce a source "
    "that is not provided. If the retrieved context does not support a "
    "claim, say that the available retrieved evidence does not establish "
    "that claim.\n\n"

    "The explanation must remain faithful to the upstream pipeline and "
    "must not present speculation as fact."
)


def _format_feature_summary(feature_vector: dict[str, Any]) -> str:
    """
    Render selected feature-vector fields.

    Generic binary features are provided as context only. The LLM must not
    assume that these features caused a particular ML prediction unless
    explicit evidence establishes that relationship.
    """

    keys = (
        "architecture",
        "binary_size",
        "entropy",
        "instruction_count",
        "section_count",
        "symbol_count",
        "known_crypto_library",
    )

    lines = [
        f"- {key}: {feature_vector.get(key)}"
        for key in keys
        if key in feature_vector
    ]

    crypto_evidence = feature_vector.get("crypto_evidence")

    if crypto_evidence:
        matched = [
            name
            for name, present in crypto_evidence.items()
            if present
        ]

        if matched:
            lines.append(
                f"- crypto_evidence matched: {', '.join(matched)}"
            )
        else:
            lines.append(
                "- crypto_evidence matched: none"
            )

    return (
        "\n".join(lines)
        if lines
        else "(no feature vector fields available)"
    )


def _format_retrieved_context(
    retrieved_documents: list[dict[str, Any]],
) -> str:
    """
    Render retrieved knowledge-base chunks as labeled evidence.

    Each source receives a label that can be referenced by the LLM.
    """

    if not retrieved_documents:
        return "(no supporting documents were retrieved)"

    blocks = []

    for index, document in enumerate(
        retrieved_documents,
        start=1,
    ):
        metadata = document.get("metadata", {})

        label = (
            metadata.get("identifier")
            or metadata.get("title")
            or f"Source {index}"
        )

        content = document.get(
            "content",
            "",
        )

        similarity = document.get(
            "similarity",
            "unknown",
        )

        blocks.append(
            f"[{label}]\n"
            f"Similarity: {similarity}\n"
            f"{content}"
        )

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
    """
    Build the complete structured explanation prompt.

    The prompt explicitly separates:
    1. upstream ML results,
    2. available binary features,
    3. risk decisions,
    4. recommendations,
    5. external retrieved evidence.

    This prevents the LLM from treating generic binary features as
    automatically causal evidence for an ML prediction.
    """

    risk_factor_lines = "\n".join(
        (
            f"- factor: {factor.get('factor')}; "
            f"weight: {factor.get('weight')}; "
            f"contribution: {factor.get('contribution')}"
        )
        for factor in risk_factors
    ) or "(no risk factors triggered)"

    recommendation_lines = (
        "\n".join(
            f"- {recommendation}"
            for recommendation in recommendations
        )
        or "(no recommendations)"
    )

    prompt = f"""
{SYSTEM_INSTRUCTION}

==================================================
FIRMWARE METADATA
==================================================

- filename: {firmware_metadata.get("filename", "unknown")}
- file_hash: {firmware_metadata.get("file_hash", "unknown")}
- upload_time: {firmware_metadata.get("upload_time", "unknown")}


==================================================
BINARY FEATURES
==================================================

The following features are supplied as observed/static-analysis data.

IMPORTANT:
These features are NOT automatically evidence that caused the ML
prediction. Only treat a feature as prediction evidence when the prompt
explicitly identifies it as algorithm-specific evidence.

{_format_feature_summary(feature_vector)}


==================================================
UPSTREAM ML CLASSIFICATION RESULT
==================================================

- algorithm family: {algorithm_family}
- detected algorithm: {algorithm}
- confidence: {confidence}%

IMPORTANT:
The algorithm and family above are already-produced results from the
upstream ML classification pipeline.

Do NOT change them.

Do NOT invent additional reasons for the classification.

If explicit algorithm-specific evidence is not present in the supplied
feature vector, state that the upstream ML pipeline produced the
classification but the available context does not provide its exact
feature-level basis.


==================================================
UPSTREAM RISK ASSESSMENT
==================================================

- risk score: {risk_score}
- risk level: {risk_level}

Triggered risk factors:

{risk_factor_lines}

IMPORTANT:
Explain the risk score using only the supplied risk factors and their
contributions.

Do NOT invent missing weights or contributions.

Do NOT create additional risk factors.


==================================================
UPSTREAM RECOMMENDATIONS
==================================================

{recommendation_lines}

IMPORTANT:
Do NOT add new recommendations.

Explain the supplied recommendations using the supplied risk factors
and retrieved evidence only.


==================================================
RETRIEVED REFERENCE CONTEXT
==================================================

The following documents were retrieved from the CryptoSage knowledge base.

These documents are the ONLY external sources that may be cited.

{_format_retrieved_context(retrieved_documents)}


==================================================
TASK
==================================================

Using ONLY the information provided above, produce an explanation with
EXACTLY these five sections.

Do not add an introduction before section 1.
Do not add a conclusion after section 5.

1. Algorithm Detection

Explain the already-produced algorithm and algorithm-family
classification.

Use explicit algorithm-specific evidence if it is present, such as:

- crypto_evidence
- matched cryptographic constants
- symbols
- known cryptographic libraries
- other explicitly identified algorithm-specific indicators

DO NOT claim that generic features such as entropy, section count,
symbol count, binary size, or instruction count caused the classification
unless the supplied context explicitly establishes that relationship.

If the prompt does not provide sufficient algorithm-specific evidence,
state clearly that the classification was produced by the upstream ML
pipeline and that the available context does not establish the exact
feature-level basis.


2. Confidence Explanation

Explain what the supplied {confidence}% confidence value represents.

State that it is the confidence reported by the upstream algorithm
classifier.

DO NOT invent feature-level explanations for the confidence.

DO NOT claim that particular features increased or decreased confidence
unless the prompt explicitly provides that information.

Do not modify the confidence value.


3. Risk Assessment Explanation

Explain why the firmware received a risk score of {risk_score}
and risk level "{risk_level}".

Use only the explicitly supplied triggered risk factors and their
contributions.

Do not invent additional risk factors.

Do not invent missing weights or contributions.

Do not change the risk score or risk level.


4. Recommendation Justification

Explain why each supplied recommendation was produced.

Tie each recommendation to the supplied risk factor(s) when the
relationship is explicitly available.

Use retrieved reference documents only when their content supports the
recommendation.

Do not introduce new recommendations.


5. Referenced Standards

List ONLY the retrieved sources that actually support statements made
in the explanation.

Use exactly the source labels shown in the Retrieved Reference Context.

Do not cite a source that was not retrieved.

Do not invent:

- standards
- RFC numbers
- CWE identifiers
- CVE identifiers
- NIST publications
- MITRE identifiers
- OWASP documents
- CISA documents

If no retrieved source supports a particular statement, do not cite one
artificially.

==================================================
STRICT GROUNDING RULES
==================================================

1. Never invent evidence.

2. Never infer feature importance from generic binary features.

3. Never claim that entropy, section count, symbol count, binary size,
   instruction count, or similar generic features caused an algorithm
   prediction unless explicitly established by the supplied context.

4. Never change the ML prediction.

5. Never change the confidence value.

6. Never change the risk score.

7. Never change the risk level.

8. Never add risk factors.

9. Never add recommendations.

10. Never invent references.

11. Never cite a document that was not retrieved.

12. Retrieved documents may justify security claims, but they must not
    be used to override the upstream ML/risk/recommendation results.

13. If information is missing, explicitly say that the available
    context does not establish it.

14. Keep the explanation concise, technical, and evidence-based.

15. Do not use Markdown bold markers such as **.

16. Do not use decorative symbols.

17. Do not output JSON.

18. Output exactly the five numbered sections requested above.
"""

    logger.debug(
        "Prompt constructed: %d characters, %d retrieved document(s).",
        len(prompt),
        len(retrieved_documents),
    )

    return prompt