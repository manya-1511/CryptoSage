"""
rag/explain.py

Phase 7 -- Explanation generation: retrieval + prompt construction +
local LLM (Ollama / Llama 3.1 8B Instruct) generation, with a
deterministic template-based fallback when Ollama is unreachable.

This module produces the final, structured, evidence-backed
explanation returned by `POST /explain/{firmware_id}`. It does not
make security decisions -- every fact it explains (algorithm, family,
confidence, risk score, risk factors, recommendations) was already
decided by earlier phases (ML prediction, risk assessment,
recommendation engine); this module only explains and cites evidence
for those already-made decisions.

**Local inference only** -- `OllamaClient` talks to a local Ollama
server (`settings.OLLAMA_BASE_URL`, default `http://localhost:11434`)
and never calls a paid/hosted API. If Ollama is not installed/running
(as in this development sandbox, which has no network access to
download the ~4-5 GB Llama 3.1 8B model weights), generation falls
back to `generate_template_explanation()` -- a deterministic,
non-hallucinating explanation built directly from the same structured
data and retrieved citations, clearly labeled as a fallback rather than
silently presented as an LLM response.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import requests

from config import get_settings
from rag.citations import Citation, citations_to_reference_strings, extract_citations
from rag.prompt import build_explanation_prompt
from rag.retriever import RetrieverError, build_retrieval_query, retrieve

logger = logging.getLogger("cryptosage.rag.explain")

settings = get_settings()


class ExplanationError(RuntimeError):
    """Raised when an explanation cannot be produced at all (missing inputs)."""


@dataclass
class ExplanationResult:
    """The complete, structured output of the explanation pipeline."""

    firmware_id: int
    algorithm: str
    confidence: float
    risk_score: float
    summary: str
    sections: dict[str, str]
    recommendations: list[str]
    references: list[str]
    retrieved_documents: list[dict[str, Any]] = field(default_factory=list)
    generated_by: str = "template_fallback"
    generation_time_ms: float = 0.0
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class OllamaClient:
    """Minimal local client for Ollama's `/api/generate` HTTP endpoint.

    Never calls a paid/hosted API -- `base_url` defaults to a local
    Ollama server. Every method degrades gracefully (returns `None`,
    never raises) on connection failure, timeout, or a non-200
    response, so the caller can fall back to the deterministic
    template explanation.
    """

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None, timeout: Optional[int] = None) -> None:
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.OLLAMA_MODEL
        self.timeout = timeout or settings.OLLAMA_TIMEOUT_SECONDS

    def is_available(self) -> bool:
        """Check whether a local Ollama server is reachable."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def generate(self, prompt: str) -> Optional[str]:
        """Generate a completion for `prompt`. Returns None on any failure."""
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            logger.warning("Ollama request failed (%s); no local LLM available.", exc)
            return None

        if response.status_code != 200:
            logger.warning("Ollama returned HTTP %d; treating as unavailable.", response.status_code)
            return None

        try:
            return response.json().get("response", "").strip() or None
        except ValueError as exc:
            logger.warning("Could not parse Ollama response as JSON: %s", exc)
            return None


def _parse_llm_sections(llm_text: str) -> dict[str, str]:
    """Best-effort split of the LLM's free-text response into the five
    required sections, keyed by section name. Falls back to putting the
    whole response under "Algorithm Detection" if section headers
    aren't found, so no LLM output is ever silently discarded.
    """
    section_names = [
        "Algorithm Detection", "Confidence Explanation", "Risk Assessment Explanation",
        "Recommendation Justification", "Referenced Standards",
    ]
    sections: dict[str, str] = {}
    remaining = llm_text
    for i, name in enumerate(section_names):
        marker = None
        for candidate in (f"{i + 1}. {name}", name):
            if candidate in remaining:
                marker = candidate
                break
        if marker is None:
            continue
        start = remaining.index(marker) + len(marker)
        next_markers = [
            remaining.index(m, start) for later in section_names[i + 1:]
            for m in (f"{section_names.index(later) + 1}. {later}", later)
            if m in remaining[start:]
        ]
        end = min(next_markers) if next_markers else len(remaining)
        sections[name] = remaining[start:end].strip(" \n:-")

    if not sections:
        sections["Algorithm Detection"] = llm_text.strip()
    return sections


def generate_template_explanation(
    algorithm: str,
    algorithm_family: str,
    confidence: float,
    risk_score: float,
    risk_level: str,
    risk_factors: list[dict[str, Any]],
    recommendations: list[str],
    retrieved_documents: list[dict[str, Any]],
) -> dict[str, str]:
    """Deterministic, template-based explanation (no LLM).

    Used when Ollama is unavailable. Every sentence is built directly
    from the already-computed structured data and the retrieved
    citations -- nothing is invented, so this trivially satisfies the
    "no hallucination" requirement, just without an LLM's fluency.
    """
    citations = extract_citations(retrieved_documents)
    reference_list = ", ".join(citations_to_reference_strings(citations)) or "no supporting documents were retrieved"

    triggered = [f for f in risk_factors if f.get("contribution", 0) > 0]
    triggered_names = ", ".join(f["factor"] for f in triggered) or "none"

    sections = {
        "Algorithm Detection": (
            f"The firmware binary was classified as implementing {algorithm} "
            f"(cryptographic family: {algorithm_family}) based on static "
            f"binary-level evidence -- matched cryptographic constants and/or "
            f"symbol names consistent with {algorithm} implementations, as "
            f"identified by the CryptoSage feature-extraction and hierarchical "
            f"classification pipeline."
        ),
        "Confidence Explanation": (
            f"The model reported a confidence of {confidence}% for this "
            f"prediction, reflecting the predicted-class probability from the "
            f"algorithm-stage classifier. Confidence below the pipeline's "
            f"low-confidence threshold causes the risk assessment to partially "
            f"discount algorithm-dependent risk factors (see the risk "
            f"assessment methodology); at {confidence}%, that adjustment "
            f"{'was applied' if confidence < 50 else 'was not applied'}."
        ),
        "Risk Assessment Explanation": (
            f"The firmware received a risk score of {risk_score} ({risk_level}), "
            f"determined by the following triggered risk factor(s): {triggered_names}. "
            f"Each factor's weighted contribution to the overall score is stored "
            f"and available in the `risk_factors` evidence."
        ),
        "Recommendation Justification": (
            ("The following recommendations were generated, each directly tied "
             f"to a triggered risk factor: {'; '.join(recommendations)}.")
            if recommendations
            else "No recommendations were generated, as no risk factors triggered above their configured thresholds."
        ),
        "Referenced Standards": f"This explanation is grounded in: {reference_list}.",
    }
    return sections


def _build_summary(sections: dict[str, str], algorithm: str, risk_level: str) -> str:
    """Build the short top-level `summary` field from the detailed sections."""
    detection = sections.get("Algorithm Detection", "")
    risk = sections.get("Risk Assessment Explanation", "")
    combined = f"{detection} {risk}".strip()
    if len(combined) > 500:
        combined = combined[:497] + "..."
    return combined or f"{algorithm} detected; overall risk level: {risk_level}."


def explain_firmware(
    firmware_id: int,
    firmware_metadata: dict[str, Any],
    feature_vector: dict[str, Any],
    algorithm: str,
    algorithm_family: str,
    confidence: float,
    risk_score: float,
    risk_level: str,
    risk_factors: list[dict[str, Any]],
    recommendations: list[str],
    top_k: Optional[int] = None,
) -> ExplanationResult:
    """Run the full Phase 7 explanation pipeline for one binary's results.

    Retrieval -> prompt construction -> local LLM generation (or
    deterministic template fallback if Ollama is unavailable) ->
    citation extraction -> structured result.

    Raises:
        ExplanationError: if required inputs (`algorithm`,
            `feature_vector`) are missing.
    """
    if not algorithm:
        message = "Cannot generate an explanation: no predicted algorithm was provided."
        logger.error(message)
        raise ExplanationError(message)
    if not feature_vector:
        message = "Cannot generate an explanation: no feature vector was provided."
        logger.error(message)
        raise ExplanationError(message)

    started_at = time.perf_counter()

    query = build_retrieval_query(
        algorithm, algorithm_family,
        [f["factor"] for f in risk_factors if f.get("contribution", 0) > 0],
        recommendations,
    )
    try:
        retrieved_documents = retrieve(query, top_k=top_k)
    except RetrieverError as exc:
        logger.warning("Retrieval unavailable (%s); proceeding with no retrieved context.", exc)
        retrieved_documents = []

    ollama_client = OllamaClient()
    generated_by = "template_fallback"
    sections: dict[str, str]

    if ollama_client.is_available():
        prompt = build_explanation_prompt(
            firmware_metadata, feature_vector, algorithm, algorithm_family, confidence,
            risk_score, risk_level, risk_factors, recommendations, retrieved_documents,
        )
        logger.info("Prompt construction completed; requesting local LLM generation (%s).", ollama_client.model)
        llm_response = ollama_client.generate(prompt)
        if llm_response:
            sections = _parse_llm_sections(llm_response)
            generated_by = f"ollama:{ollama_client.model}"
            logger.info("LLM response received (%d characters).", len(llm_response))
        else:
            logger.warning("Ollama was reachable but returned no usable response; using template fallback.")
            sections = generate_template_explanation(
                algorithm, algorithm_family, confidence, risk_score, risk_level,
                risk_factors, recommendations, retrieved_documents,
            )
    else:
        logger.info(
            "Ollama is not reachable at %s; generating a deterministic template-based "
            "explanation instead of an LLM response.", ollama_client.base_url,
        )
        sections = generate_template_explanation(
            algorithm, algorithm_family, confidence, risk_score, risk_level,
            risk_factors, recommendations, retrieved_documents,
        )

    citations = extract_citations(retrieved_documents)
    references = citations_to_reference_strings(citations)
    logger.info("Citation generation completed: %d reference(s).", len(references))

    summary = _build_summary(sections, algorithm, risk_level)
    generation_time_ms = round((time.perf_counter() - started_at) * 1000, 2)

    logger.info(
        "Explanation generation completed: firmware_id=%s, generated_by=%s, time=%.2fms",
        firmware_id, generated_by, generation_time_ms,
    )

    return ExplanationResult(
        firmware_id=firmware_id,
        algorithm=algorithm,
        confidence=confidence,
        risk_score=risk_score,
        summary=summary,
        sections=sections,
        recommendations=recommendations,
        references=references,
        retrieved_documents=retrieved_documents,
        generated_by=generated_by,
        generation_time_ms=generation_time_ms,
    )
