from __future__ import annotations

from unittest.mock import patch

import requests

import rag.explain as explain_mod
from rag.explain import ExplanationError, OllamaClient, explain_firmware

GOOD_LLM_TEXT = """1. Algorithm Detection
The upstream classifier identified AES, supported by matched AES S-box constants [FIPS 197].
2. Confidence Explanation
The classifier reported 87.5 percent confidence for this prediction.
3. Risk Assessment Explanation
The firmware received a risk score of 42.0 at medium risk, driven by weak_key_length [CWE-327].
4. Recommendation Justification
Upgrading key management addresses the weak_key_length risk factor [SP 800-57].
5. Referenced Standards
FIPS 197, CWE-327, SP 800-57
"""

FIRMWARE_KWARGS = dict(
    firmware_id=1,
    firmware_metadata={"filename": "router_fw.bin"},
    feature_vector={"architecture": "ARM", "crypto_evidence": {"aes_sbox_constants": True}},
    algorithm="AES",
    algorithm_family="symmetric",
    confidence=87.5,
    risk_score=42.0,
    risk_level="medium",
    risk_factors=[{"factor": "weak_key_length", "weight": 0.4, "contribution": 12.0}],
    recommendations=["Upgrade key management practices"],
)


def test_ollama_unavailable_uses_template_fallback(ingested_kb):
    with patch.object(OllamaClient, "is_available", return_value=False):
        result = explain_firmware(**FIRMWARE_KWARGS)
    assert result.generated_by == "template_fallback"
    assert result.llm_generation_time_ms == 0.0


def test_successful_qwen_response_is_used(ingested_kb):
    with patch.object(OllamaClient, "is_available", return_value=True), \
         patch.object(OllamaClient, "generate", return_value=GOOD_LLM_TEXT):
        result = explain_firmware(**FIRMWARE_KWARGS)
    assert result.generated_by == "ollama:qwen2.5:3b"
    assert result.citation_validation["valid"] is True
    assert set(result.sections.keys()) >= {
        "Algorithm Detection", "Confidence Explanation", "Risk Assessment Explanation",
        "Recommendation Justification", "Referenced Standards",
    }


def test_ollama_timeout_falls_back_to_template(ingested_kb):
    with patch.object(OllamaClient, "is_available", return_value=True), \
         patch("rag.explain.requests.post", side_effect=requests.Timeout("simulated timeout")):
        result = explain_firmware(**FIRMWARE_KWARGS)
    assert result.generated_by == "template_fallback"


def test_malformed_response_falls_back_to_template(ingested_kb):
    with patch.object(OllamaClient, "is_available", return_value=True), \
         patch.object(OllamaClient, "generate", return_value=None):
        result = explain_firmware(**FIRMWARE_KWARGS)
    assert result.generated_by == "template_fallback"


def test_missing_sections_falls_back_to_template(ingested_kb):
    with patch.object(OllamaClient, "is_available", return_value=True), \
         patch.object(OllamaClient, "generate", return_value="1. Algorithm Detection\nAES detected.\n"):
        result = explain_firmware(**FIRMWARE_KWARGS)
    assert result.generated_by == "template_fallback"
    assert result.citation_validation["valid"] is False


def test_invalid_citation_falls_back_to_template(ingested_kb):
    bad_text = GOOD_LLM_TEXT.replace("[FIPS 197]", "[MADE_UP_STANDARD_9999]")
    with patch.object(OllamaClient, "is_available", return_value=True), \
         patch.object(OllamaClient, "generate", return_value=bad_text):
        result = explain_firmware(**FIRMWARE_KWARGS)
    assert result.generated_by == "template_fallback"
    assert "MADE_UP_STANDARD_9999" in result.citation_validation["invalid_citations"]


def test_ollama_client_never_raises_on_connection_error():
    client = OllamaClient(base_url="http://localhost:1", timeout=1)
    assert client.is_available() is False
    assert client.generate("hello") is None


def test_missing_algorithm_raises_explanation_error(ingested_kb):
    kwargs = dict(FIRMWARE_KWARGS)
    kwargs["algorithm"] = ""
    try:
        explain_firmware(**kwargs)
        assert False, "expected ExplanationError"
    except ExplanationError:
        pass


def test_missing_feature_vector_raises_explanation_error(ingested_kb):
    kwargs = dict(FIRMWARE_KWARGS)
    kwargs["feature_vector"] = {}
    try:
        explain_firmware(**kwargs)
        assert False, "expected ExplanationError"
    except ExplanationError:
        pass


def test_generated_by_label_is_never_ambiguous_between_llm_and_fallback(ingested_kb):
    with patch.object(OllamaClient, "is_available", return_value=True), \
         patch.object(OllamaClient, "generate", return_value=GOOD_LLM_TEXT):
        llm_result = explain_firmware(**FIRMWARE_KWARGS)
    with patch.object(OllamaClient, "is_available", return_value=False):
        fallback_result = explain_firmware(**FIRMWARE_KWARGS)
    assert llm_result.generated_by.startswith("ollama:")
    assert fallback_result.generated_by == "template_fallback"
    assert llm_result.generated_by != fallback_result.generated_by
