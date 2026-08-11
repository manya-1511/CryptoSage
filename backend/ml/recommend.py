"""
ml/recommend.py

Phase 6/7 -- Rule-Based Security Recommendation Engine.

Turns the evidence-backed `RiskFactor`s produced by `ml/risk.py` into
specific, actionable, deterministic recommendations. **No AI or LLM is
used** -- every recommendation is a direct, configured lookup keyed by
the exact factor that triggered it (`ml/recommendation_rules.json`),
so the same risk assessment always produces the same recommendations,
and adding a new rule/algorithm/recommendation is a configuration
change, never a code change.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

from config import get_settings
from ml.risk import RiskFactor

logger = logging.getLogger("cryptosage.ml.recommend")

settings = get_settings()

# Maps a RiskFactor's `category` to the corresponding section of
# recommendation_rules.json, and the sub-factor lookup key naming
# convention used within it (matches ml/risk.py's `add()` `key`
# arguments, e.g. "writable_executable_section").
_CATEGORY_TO_RULES_SECTION: dict[str, str] = {
    "binary_security": "binary_security_recommendations",
    "firmware_metadata": "firmware_metadata_recommendations",
}

# Reverse mapping from a RiskFactor's human-readable `factor` name back
# to the snake_case rule key used in recommendation_rules.json, since
# ml/risk.py reports factors by display name, not by config key.
_FACTOR_NAME_TO_RULE_KEY: dict[str, str] = {
    "Writable Executable Sections": "writable_executable_section",
    "Debug Symbols": "debug_symbols_present",
    "High Entropy": "high_entropy",
    "Missing Symbols": "missing_symbols",
    "Suspicious Imports": "suspicious_imports",
    "Hardcoded Cryptographic Constants": "hardcoded_crypto_constants",
    "Weak Compiler Protections": "weak_compiler_protections",
    "Large Executable Surface": "large_executable_surface",
    "Missing Relocation Protection (No PIE)": "missing_relocation_protection",
    "Missing Stack Protection": "missing_stack_protection",
    "Unknown Compiler": "unknown_compiler",
    "Old Compiler Version": "old_compiler",
    "Architecture Mismatch": "architecture_mismatch",
    "Missing Metadata": "missing_metadata",
    "Firmware Age": "firmware_age",
}


class RecommendationConfigError(RuntimeError):
    """Raised when `recommendation_rules.json` is missing or malformed."""


@lru_cache(maxsize=1)
def load_recommendation_rules(config_path: Optional[Path] = None) -> dict:
    """Load and cache `recommendation_rules.json`.

    Raises:
        RecommendationConfigError: if the file is missing or not valid JSON.
    """
    path = config_path or settings.RECOMMENDATION_RULES_PATH
    if not path.exists():
        message = f"Recommendation rules not found at {path}."
        logger.error(message)
        raise RecommendationConfigError(message)
    try:
        rules = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        message = f"Recommendation rules at {path} are not valid JSON: {exc}"
        logger.error(message)
        raise RecommendationConfigError(message) from exc

    logger.info("Recommendation rules loaded from %s", path)
    return rules


def reset_recommendation_rules_cache() -> None:
    """Clear the cached recommendation rules, forcing a reload on next use."""
    load_recommendation_rules.cache_clear()


def _recommendation_for_factor(risk_factor: RiskFactor, rules: dict) -> Optional[str]:
    """Look up the configured recommendation text for one triggered factor."""
    if risk_factor.category == "deprecated_algorithm":
        # `risk_factor.factor` is e.g. "Deprecated SHA1"; the algorithm
        # name is the last whitespace-separated token.
        algorithm = risk_factor.factor.replace("Deprecated ", "").strip()
        specific = rules.get("algorithm_recommendations", {}).get(algorithm)
        if specific:
            return specific
        return rules.get("deprecated_algorithm_generic_recommendation")

    if risk_factor.category == "algorithm_strength":
        # Only recommend on the strength factor if it wasn't already
        # covered by a deprecated-algorithm recommendation (avoids a
        # duplicate/near-duplicate recommendation for the same algorithm).
        return None

    section_name = _CATEGORY_TO_RULES_SECTION.get(risk_factor.category)
    if section_name is None:
        return None
    rule_key = _FACTOR_NAME_TO_RULE_KEY.get(risk_factor.factor)
    if rule_key is None:
        return None
    return rules.get(section_name, {}).get(rule_key)


def generate_recommendations(
    risk_factors: list[RiskFactor],
    algorithm: Optional[str] = None,
) -> list[str]:
    """Generate the deduplicated, ordered list of recommendations for one assessment.

    Only factors that actually **triggered** (`contribution > 0`)
    produce a recommendation -- a risk factor that was evaluated and
    found not to apply generates no advice. If a specific algorithm was
    identified as deprecated, its algorithm-specific recommendation
    takes priority over the generic deprecated-algorithm message.

    Args:
        risk_factors: The `RiskFactor` list from `ml.risk.assess_risk()`.
        algorithm: The predicted algorithm (used only for logging).

    Returns:
        An ordered list of unique recommendation strings. Never raises
        for an individual factor with no matching rule -- it is simply
        skipped (logged at debug level).
    """
    rules = load_recommendation_rules()

    recommendations: list[str] = []
    seen: set[str] = set()

    triggered_factors = [rf for rf in risk_factors if rf.contribution > 0]
    for risk_factor in triggered_factors:
        recommendation = _recommendation_for_factor(risk_factor, rules)
        if recommendation is None:
            logger.debug("No recommendation rule configured for factor '%s'.", risk_factor.factor)
            continue
        if recommendation not in seen:
            recommendations.append(recommendation)
            seen.add(recommendation)

    logger.info(
        "Generated %d recommendation(s) for algorithm=%s from %d triggered factor(s).",
        len(recommendations), algorithm, len(triggered_factors),
    )
    return recommendations
