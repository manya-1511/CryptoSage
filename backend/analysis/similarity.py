"""
analysis/similarity.py

Cosine similarity between two binaries' feature vectors.

Purpose: compare an uploaded binary against previously analyzed
binaries to answer "how similar is this to something we've already
seen?" -- for example, to surface related samples for a human analyst.

This module is explicitly **not** used for ML classification; it has
no notion of labels or a trained model, only vector geometry.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import numpy as np

logger = logging.getLogger("cryptosage.analysis.similarity")

# The numeric feature keys compared by default when no explicit key
# list is given. Chosen to be present on every binary regardless of
# architecture or crypto content, so a similarity score is always
# computable. Boolean crypto-evidence flags are intentionally excluded
# by default since they behave more like categorical labels than
# continuous similarity dimensions; pass an explicit `keys` list to
# include them if desired.
DEFAULT_SIMILARITY_KEYS: list[str] = [
    "binary_size", "entropy", "entry_point", "section_count",
    "segment_count", "symbol_count", "import_count", "export_count",
    "string_count", "instruction_count",
]


def feature_vector_to_array(features: dict[str, Any], keys: Optional[list[str]] = None) -> np.ndarray:
    """Convert a subset of a feature dict into a fixed-order numeric array.

    Missing or non-numeric values become `0.0` so two feature dicts with
    different available fields can still be compared; this is a
    similarity-geometry convenience, not a claim that the value is
    actually zero.
    """
    keys = keys or DEFAULT_SIMILARITY_KEYS
    values: list[float] = []
    for key in keys:
        value = features.get(key)
        try:
            values.append(float(value) if value is not None else 0.0)
        except (TypeError, ValueError):
            values.append(0.0)
    return np.array(values, dtype=np.float64)


def cosine_similarity(vector_a: np.ndarray, vector_b: np.ndarray) -> Optional[float]:
    """Compute the cosine similarity between two numeric vectors.

    Returns a value in [-1.0, 1.0] (typically [0, 1] for non-negative
    feature vectors), or `None` if either vector has zero magnitude
    (cosine similarity is undefined for a zero vector).
    """
    if vector_a.shape != vector_b.shape:
        logger.warning(
            "Cannot compute cosine similarity for vectors of different shape: %s vs %s",
            vector_a.shape, vector_b.shape,
        )
        return None

    norm_a = np.linalg.norm(vector_a)
    norm_b = np.linalg.norm(vector_b)
    if norm_a == 0 or norm_b == 0:
        logger.debug("Cosine similarity undefined for a zero-magnitude vector.")
        return None

    similarity = float(np.dot(vector_a, vector_b) / (norm_a * norm_b))
    # Guard against tiny floating-point overshoot outside [-1, 1].
    return max(-1.0, min(1.0, similarity))


def compare_binaries(
    features_a: dict[str, Any],
    features_b: dict[str, Any],
    keys: Optional[list[str]] = None,
) -> Optional[float]:
    """Compute the cosine similarity between two binaries' feature dicts.

    Convenience wrapper combining `feature_vector_to_array` and
    `cosine_similarity` for the common case of comparing two
    `analysis.features.extract_features()` outputs directly.
    """
    vector_a = feature_vector_to_array(features_a, keys)
    vector_b = feature_vector_to_array(features_b, keys)
    return cosine_similarity(vector_a, vector_b)


def find_most_similar(
    target_features: dict[str, Any],
    candidates: list[dict[str, Any]],
    keys: Optional[list[str]] = None,
    top_n: int = 5,
) -> list[tuple[int, float]]:
    """Rank a list of candidate feature dicts by similarity to a target.

    Returns up to `top_n` (candidate_index, similarity_score) pairs,
    sorted by descending similarity. Candidates whose similarity is
    undefined (zero-magnitude vector) are excluded rather than assigned
    a fabricated score.
    """
    scored: list[tuple[int, float]] = []
    for index, candidate in enumerate(candidates):
        score = compare_binaries(target_features, candidate, keys)
        if score is not None:
            scored.append((index, score))

    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:top_n]
