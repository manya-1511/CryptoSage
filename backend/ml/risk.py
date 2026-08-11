"""
ml/risk.py

Phase 6/7 -- Firmware Risk Assessment Engine.

Computes a deterministic, explainable, weighted multi-factor security
risk score for a firmware binary from data already produced by earlier
phases: the ML prediction (algorithm, family, confidence -- Phase 5B/6),
the static feature vector (Phase 4's `analysis.features.extract_features()`
output), optional richer binary structural metadata (Phase 4's
`analysis.binary.parse_elf()` output), and firmware metadata (Phase 3's
`firmware` table row).

**This module does not use a machine learning model.** Every score is
computed from configured weights and thresholds
(`ml/risk_config.json`) applied to concrete, logged evidence -- the
same inputs always produce the same output, and every point of the
final score traces back to a named, weighted factor.

    Risk Score = sum(category_weight x normalized_category_factor)

capped to [0, 100], with a bounded confidence-based dampening applied
only to the algorithm-identification-dependent factors (see
`_apply_confidence_adjustment`).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from config import get_settings

logger = logging.getLogger("cryptosage.ml.risk")

settings = get_settings()


class RiskConfigError(RuntimeError):
    """Raised when `risk_config.json` is missing, malformed, or invalid."""


@dataclass
class RiskFactor:
    """One scored, evidence-backed contributor to the overall risk score."""

    factor: str
    category: str
    weight: float
    contribution: float
    evidence: str


@dataclass
class RiskAssessment:
    """The complete result of assessing one binary's firmware risk."""

    firmware_id: int
    algorithm: str
    algorithm_family: str
    confidence: float
    risk_score: float
    risk_level: str
    risk_factors: list[RiskFactor] = field(default_factory=list)
    category_scores: dict[str, float] = field(default_factory=dict)
    assessed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# --------------------------------------------------------------------------
# Configuration loading
# --------------------------------------------------------------------------

@lru_cache(maxsize=1)
def load_risk_config(config_path: Optional[Path] = None) -> dict[str, Any]:
    """Load and cache `risk_config.json`.

    Raises:
        RiskConfigError: if the file is missing or not valid JSON, or is
            missing a required top-level section.
    """
    path = config_path or settings.RISK_CONFIG_PATH
    if not path.exists():
        message = f"Risk configuration not found at {path}."
        logger.error(message)
        raise RiskConfigError(message)
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        message = f"Risk configuration at {path} is not valid JSON: {exc}"
        logger.error(message)
        raise RiskConfigError(message) from exc

    required_sections = (
        "category_weights", "algorithm_strength_scores", "deprecated_algorithms",
        "binary_security_weights", "firmware_metadata_weights", "risk_levels",
    )
    missing = [section for section in required_sections if section not in config]
    if missing:
        message = f"Risk configuration at {path} is missing required section(s): {missing}"
        logger.error(message)
        raise RiskConfigError(message)

    logger.info("Risk configuration loaded from %s", path)
    return config


def reset_risk_config_cache() -> None:
    """Clear the cached risk configuration, forcing a reload on next use."""
    load_risk_config.cache_clear()


# --------------------------------------------------------------------------
# Factor 1 + 2: Cryptographic algorithm strength / deprecation
# --------------------------------------------------------------------------

def _algorithm_strength_factor(algorithm: str, config: dict[str, Any]) -> RiskFactor:
    """Score the intrinsic strength of the identified algorithm.

    A continuous [0, 1] "weakness" score per algorithm, configured in
    `algorithm_strength_scores` (0 = very strong, 1 = very weak). An
    algorithm with no configured entry falls back to
    `_default_unknown_algorithm` (treated as moderate/unknown risk)
    rather than silently scoring zero risk for something never assessed.
    """
    scores = config["algorithm_strength_scores"]
    weight = config["category_weights"]["algorithm_strength"]
    normalized = scores.get(algorithm, scores.get("_default_unknown_algorithm", 0.5))
    contribution = round(weight * normalized, 4)
    evidence = f"Algorithm '{algorithm}' strength score = {normalized} (0=strong, 1=weak)."
    return RiskFactor("Algorithm Strength", "algorithm_strength", weight, contribution, evidence)


def _deprecated_algorithm_factor(algorithm: str, config: dict[str, Any]) -> RiskFactor:
    """Flag algorithms explicitly deprecated by standards bodies (NIST/OWASP)."""
    weight = config["category_weights"]["deprecated_algorithm"]
    is_deprecated = algorithm in config["deprecated_algorithms"]
    contribution = weight if is_deprecated else 0.0
    evidence = (
        f"'{algorithm}' is on the deprecated-algorithm list."
        if is_deprecated
        else f"'{algorithm}' is not flagged as deprecated."
    )
    factor_name = f"Deprecated {algorithm}" if is_deprecated else "No Deprecated Algorithm Detected"
    return RiskFactor(factor_name, "deprecated_algorithm", weight, contribution, evidence)


# --------------------------------------------------------------------------
# Factor 3: Binary security
# --------------------------------------------------------------------------

def _binary_security_factors(
    feature_vector: dict[str, Any],
    binary_metadata: Optional[dict[str, Any]],
    config: dict[str, Any],
) -> list[RiskFactor]:
    """Evaluate every configured binary-security sub-factor.

    Reads primarily from `feature_vector` (Phase 4's
    `extract_features()` output, always available), and from the
    richer `binary_metadata` (Phase 4's `parse_elf()` output --
    imported function names, ELF file type -- if the caller supplied
    it) for the sub-factors that need data the flat feature vector
    doesn't carry. A sub-factor whose underlying signal isn't available
    in either source contributes 0 and is logged as "unknown" rather
    than being silently assumed safe or risky.
    """
    weights = config["binary_security_weights"]
    thresholds = config["thresholds"]
    binary_metadata = binary_metadata or {}
    factors: list[RiskFactor] = []

    def add(key: str, name: str, triggered: bool, evidence: str) -> None:
        weight = weights.get(key, 0)
        contribution = weight if triggered else 0.0
        factors.append(RiskFactor(name, "binary_security", weight, contribution, evidence))

    # Writable + executable section (W^X violation).
    executable_ratio = feature_vector.get("executable_section_ratio")
    writable_ratio = feature_vector.get("writable_section_ratio")
    wx_violation = bool(executable_ratio and writable_ratio and executable_ratio > 0 and writable_ratio > 0)
    add(
        "writable_executable_section", "Writable Executable Sections", wx_violation,
        f"executable_section_ratio={executable_ratio}, writable_section_ratio={writable_ratio}.",
    )

    # Debug symbols / unstripped build.
    optimization_hint = feature_vector.get("optimization_hints")
    debug_present = optimization_hint == "likely_debug_or_unoptimized"
    add(
        "debug_symbols_present", "Debug Symbols", debug_present,
        f"optimization_hints='{optimization_hint}'.",
    )

    # High entropy (packing / obfuscation / embedded encrypted payload).
    entropy = feature_vector.get("entropy")
    high_entropy = bool(entropy is not None and entropy >= thresholds["high_entropy_threshold"])
    add(
        "high_entropy", "High Entropy", high_entropy,
        f"entropy={entropy} (threshold={thresholds['high_entropy_threshold']}).",
    )

    # Missing symbols (fully stripped -- reduces auditability).
    symbol_count = feature_vector.get("symbol_count")
    missing_symbols = symbol_count is not None and symbol_count == 0
    add(
        "missing_symbols", "Missing Symbols", missing_symbols,
        f"symbol_count={symbol_count}.",
    )

    # Suspicious imports (needs richer binary_metadata; best-effort).
    imported_functions = binary_metadata.get("imported_functions") or []
    suspicious_list = config.get("suspicious_import_functions", [])
    matched_imports = sorted({
        name for name in imported_functions
        if any(str(name).lower() == suspicious.lower() for suspicious in suspicious_list)
    })
    add(
        "suspicious_imports", "Suspicious Imports", bool(matched_imports),
        f"matched: {matched_imports}." if matched_imports else "no imported-function data available or no matches.",
    )

    # Hardcoded crypto constants.
    crypto_evidence = feature_vector.get("crypto_evidence") or {}
    has_constants = any(bool(v) for v in crypto_evidence.values()) or any(
        bool(feature_vector.get(k)) for k in ("aes_constant", "sha_constant", "sha1_constant", "md5_constant")
    )
    add(
        "hardcoded_crypto_constants", "Hardcoded Cryptographic Constants", has_constants,
        f"crypto_evidence={crypto_evidence}.",
    )

    # Weak compiler protections (needs symbol names; best-effort).
    symbols = binary_metadata.get("symbols") or []
    has_stack_chk = any("stack_chk" in str(s).lower() for s in symbols)
    weak_protections = bool(symbols) and not has_stack_chk
    add(
        "weak_compiler_protections", "Weak Compiler Protections", weak_protections,
        "no __stack_chk_fail/__stack_chk_guard symbol found." if weak_protections else "stack protector symbol present or no symbol data available.",
    )

    # Large executable surface.
    binary_size = feature_vector.get("binary_size")
    large_surface = bool(binary_size and binary_size >= thresholds["large_binary_bytes"])
    add(
        "large_executable_surface", "Large Executable Surface", large_surface,
        f"binary_size={binary_size} bytes (threshold={thresholds['large_binary_bytes']}).",
    )

    # Missing relocation protection (PIE) -- needs ELF file_type.
    file_type = str(binary_metadata.get("file_type") or "")
    missing_pie = bool(file_type) and "DYN" not in file_type.upper() and "PIE" not in file_type.upper()
    add(
        "missing_relocation_protection", "Missing Relocation Protection (No PIE)", missing_pie,
        f"file_type='{file_type}'." if file_type else "ELF file_type not available.",
    )

    # Missing stack protection (same signal as weak_compiler_protections,
    # reported as a distinct named factor per the specification).
    add(
        "missing_stack_protection", "Missing Stack Protection", weak_protections,
        "no __stack_chk_fail/__stack_chk_guard symbol found." if weak_protections else "stack protector symbol present or no symbol data available.",
    )

    return factors


# --------------------------------------------------------------------------
# Factor 4: Firmware metadata
# --------------------------------------------------------------------------

def _parse_compiler_major_version(compiler_hints: Optional[str]) -> tuple[Optional[str], Optional[int]]:
    """Best-effort extraction of (compiler family, major version) from a
    compiler hint string like "GCC: (Ubuntu 13.3.0-...) 13.3.0" or
    "Ubuntu clang version 18.1.3 (...)".
    """
    if not compiler_hints:
        return None, None
    lowered = compiler_hints.lower()
    import re

    match = re.search(r"(\d+)\.\d+\.\d+", compiler_hints)
    major_version = int(match.group(1)) if match else None
    if "clang" in lowered:
        return "clang", major_version
    if "gcc" in lowered:
        return "gcc", major_version
    return "unknown", major_version


def _firmware_metadata_factors(
    feature_vector: dict[str, Any],
    firmware_metadata: Optional[dict[str, Any]],
    config: dict[str, Any],
) -> list[RiskFactor]:
    """Evaluate every configured firmware-metadata sub-factor."""
    weights = config["firmware_metadata_weights"]
    thresholds = config["thresholds"]
    firmware_metadata = firmware_metadata or {}
    factors: list[RiskFactor] = []

    def add(key: str, name: str, triggered: bool, evidence: str) -> None:
        weight = weights.get(key, 0)
        contribution = weight if triggered else 0.0
        factors.append(RiskFactor(name, "firmware_metadata", weight, contribution, evidence))

    compiler_hints = feature_vector.get("compiler_hints")
    unknown_compiler = not compiler_hints
    add("unknown_compiler", "Unknown Compiler", unknown_compiler, f"compiler_hints={compiler_hints!r}.")

    compiler_family, major_version = _parse_compiler_major_version(compiler_hints)
    old_compiler = False
    if major_version is not None:
        if compiler_family == "gcc" and major_version < thresholds["old_gcc_major_version"]:
            old_compiler = True
        elif compiler_family == "clang" and major_version < thresholds["old_clang_major_version"]:
            old_compiler = True
    add(
        "old_compiler", "Old Compiler Version", old_compiler,
        f"compiler={compiler_family}, major_version={major_version}.",
    )

    architecture = feature_vector.get("architecture")
    architecture_mismatch = architecture is not None and architecture not in thresholds["supported_architectures"]
    add(
        "architecture_mismatch", "Architecture Mismatch", architecture_mismatch,
        f"architecture={architecture!r}, supported={thresholds['supported_architectures']}.",
    )

    key_metadata_fields = ("architecture", "binary_size", "entropy", "entry_point")
    missing_count = sum(1 for field_name in key_metadata_fields if feature_vector.get(field_name) is None)
    missing_metadata = missing_count >= 2
    add(
        "missing_metadata", "Missing Metadata", missing_metadata,
        f"{missing_count}/{len(key_metadata_fields)} key metadata fields are null.",
    )

    firmware_age_days = firmware_metadata.get("age_days")
    old_firmware = bool(firmware_age_days is not None and firmware_age_days >= thresholds["old_firmware_age_days"])
    add(
        "firmware_age", "Firmware Age", old_firmware,
        f"age_days={firmware_age_days}." if firmware_age_days is not None else "firmware age not available.",
    )

    return factors


# --------------------------------------------------------------------------
# Confidence adjustment
# --------------------------------------------------------------------------

def _apply_confidence_adjustment(
    algorithm_factors: list[RiskFactor], confidence: float, config: dict[str, Any]
) -> list[RiskFactor]:
    """Dampen algorithm-dependent factors toward neutral when confidence is low.

    Only `algorithm_strength` and `deprecated_algorithm` factors are
    touched -- they are the only ones whose validity depends on the ML
    prediction actually being correct. The dampening is bounded by
    `minimum_trust_factor` so it can only ever pull a factor part-way
    toward neutral, never discard it (per spec: "Do NOT reduce the risk
    score dramatically").
    """
    adjustment = config.get("confidence_adjustment", {})
    threshold = adjustment.get("low_confidence_threshold", 50.0)
    if confidence >= threshold:
        return algorithm_factors

    min_trust = adjustment.get("minimum_trust_factor", 0.85)
    neutral_baseline = adjustment.get("neutral_baseline", 0.5)
    # Trust scales linearly from `min_trust` (at confidence=0) up to 1.0
    # (at confidence=threshold) -- never below min_trust.
    trust = min_trust + (1 - min_trust) * (confidence / threshold)

    adjusted: list[RiskFactor] = []
    for rf in algorithm_factors:
        neutral_contribution = rf.weight * neutral_baseline
        blended = rf.contribution * trust + neutral_contribution * (1 - trust)
        adjusted.append(RiskFactor(
            factor=rf.factor,
            category=rf.category,
            weight=rf.weight,
            contribution=round(blended, 4),
            evidence=rf.evidence + f" [confidence-adjusted: trust={round(trust, 3)}, low ML confidence={confidence}%]",
        ))
    return adjusted


# --------------------------------------------------------------------------
# Risk level mapping
# --------------------------------------------------------------------------

def _map_risk_level(score: float, config: dict[str, Any]) -> str:
    """Map a numeric 0-100 risk score to its configured textual level.

    Bands are matched by their upper bound only (score <= band["max"]),
    checked in ascending order, so a score can never fall through a gap
    between two integer band boundaries (e.g. a fractional score of
    80.5 with bands [61-80] and [81-100] configured) -- every score in
    [0, 100] is guaranteed to match some band.
    """
    for band in sorted(config["risk_levels"], key=lambda b: b["max"]):
        if score <= band["max"]:
            return band["level"]
    # Score above every configured upper bound (shouldn't happen given
    # a correctly configured 0-100 set of bands, and risk_score is
    # already capped to 100 by assess_risk) -- fall back to the highest
    # configured level rather than raising.
    logger.warning("Risk score %.2f exceeded every configured risk level band.", score)
    return max(config["risk_levels"], key=lambda b: b["max"])["level"]


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def assess_risk(
    firmware_id: int,
    algorithm: str,
    algorithm_family: str,
    confidence: float,
    feature_vector: dict[str, Any],
    binary_metadata: Optional[dict[str, Any]] = None,
    firmware_metadata: Optional[dict[str, Any]] = None,
) -> RiskAssessment:
    """Compute the full weighted, multi-factor, explainable risk assessment.

    Args:
        firmware_id: The firmware's database ID (carried through for
            logging/traceability only).
        algorithm: The ML-predicted specific algorithm (Phase 6 Stage 2).
        algorithm_family: The ML-predicted cryptographic family (Stage 1).
        confidence: The ML prediction's confidence (0-100).
        feature_vector: The raw `feature_vector.json` content produced
            by `analysis.features.extract_features()`.
        binary_metadata: Optional, richer ELF structural metadata from
            `analysis.binary.parse_elf()` (imported function names,
            symbol names, ELF file type) -- used for the binary-security
            sub-factors that need more than the flat feature vector
            carries. Factors needing this data degrade gracefully (0
            contribution, logged) when it isn't supplied.
        firmware_metadata: Optional firmware-record-level metadata
            (e.g. `{"age_days": ...}`).

    Raises:
        RiskConfigError: if `risk_config.json` is missing or invalid.
    """
    if not algorithm:
        message = "Cannot assess risk: no predicted algorithm was provided."
        logger.error(message)
        raise ValueError(message)
    if not feature_vector:
        message = "Cannot assess risk: no feature vector was provided."
        logger.error(message)
        raise ValueError(message)

    config = load_risk_config()
    logger.info(
        "Risk calculation started: firmware_id=%s, algorithm=%s, family=%s, confidence=%.2f%%",
        firmware_id, algorithm, algorithm_family, confidence,
    )

    algorithm_factors = [
        _algorithm_strength_factor(algorithm, config),
        _deprecated_algorithm_factor(algorithm, config),
    ]
    algorithm_factors = _apply_confidence_adjustment(algorithm_factors, confidence, config)

    binary_factors = _binary_security_factors(feature_vector, binary_metadata, config)
    metadata_factors = _firmware_metadata_factors(feature_vector, firmware_metadata, config)

    all_factors = algorithm_factors + binary_factors + metadata_factors
    matched_factors = [rf for rf in all_factors if rf.contribution > 0]
    logger.info(
        "Matched %d/%d risk factor(s): %s",
        len(matched_factors), len(all_factors), [rf.factor for rf in matched_factors],
    )

    raw_total = sum(rf.contribution for rf in all_factors)
    risk_score = round(min(100.0, max(0.0, raw_total)), 2)
    risk_level = _map_risk_level(risk_score, config)

    category_scores: dict[str, float] = {}
    for rf in all_factors:
        category_scores[rf.category] = round(category_scores.get(rf.category, 0.0) + rf.contribution, 2)

    logger.info(
        "Risk calculation completed: firmware_id=%s, risk_score=%.2f, risk_level=%s",
        firmware_id, risk_score, risk_level,
    )

    return RiskAssessment(
        firmware_id=firmware_id,
        algorithm=algorithm,
        algorithm_family=algorithm_family,
        confidence=confidence,
        risk_score=risk_score,
        risk_level=risk_level,
        risk_factors=all_factors,
        category_scores=category_scores,
    )
