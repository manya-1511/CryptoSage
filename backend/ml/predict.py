"""
 
Phase 6 -- Runtime Hierarchical ML Inference Engine (upgrades Phase 5B).

Loads `best_model.pkl` (a two-stage hierarchical model: a family-level
classifier plus one algorithm-level sub-model per family), consumes a
feature vector already produced by the Firmware Analysis Engine, and
returns both the predicted cryptographic family and the specific
algorithm, with a confidence score and timing.

This module never retrains anything (`ml/train.py` is untouched by it)
and never extracts features (`analysis/` is untouched by it) -- it is
inference-only, exactly like its Phase 5B predecessor. The model is
loaded once per process (`get_model_bundle()`, `lru_cache`) and reused.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import joblib
import numpy as np
import pandas as pd

from config import get_settings

try:
    import shap
except ImportError:  # pragma: no cover - explainability is optional at inference time
    shap = None

logger = logging.getLogger("cryptosage.ml.predict")

settings = get_settings()

TARGET_COLUMN = "algorithm_label"

# Raw feature-vector keys that feed a "*_normalized" training column via
# min-max scaling learned in dataset/preprocess.py.
_NORMALIZED_SOURCE_KEYS: dict[str, str] = {
    "binary_size_normalized": "binary_size",
    "entropy_normalized": "entropy",
    "entry_point_normalized": "entry_point",
    "instruction_count_normalized": "instruction_count",
    "section_count_normalized": "section_count",
    "symbol_count_normalized": "symbol_count",
    "import_count_normalized": "import_count",
    "import_libraries_normalized": "import_libraries",
    "string_count_normalized": "string_count",
    "function_count_normalized": "function_count",
    "segment_count_normalized": "segment_count",
    "export_count_normalized": "export_count",
    "jump_count_normalized": "jump_count",
    "call_count_normalized": "call_count",
    "return_count_normalized": "return_count",
    "arithmetic_count_normalized": "arithmetic_count",
    "logical_count_normalized": "logical_count",
    "memory_count_normalized": "memory_count",
    "branch_count_normalized": "branch_count",
    "instruction_entropy_normalized": "instruction_entropy",
    "unique_opcode_ratio_normalized": "unique_opcode_ratio",
    "opcode_bigram_entropy_normalized": "opcode_bigram_entropy",
    "opcode_bigram_unique_ratio_normalized": "opcode_bigram_unique_ratio",
    "opcode_trigram_entropy_normalized": "opcode_trigram_entropy",
    "opcode_trigram_unique_ratio_normalized": "opcode_trigram_unique_ratio",
    "basic_block_count_estimate_normalized": "basic_block_count_estimate",
    "cfg_edge_count_estimate_normalized": "cfg_edge_count_estimate",
    "cyclomatic_complexity_estimate_normalized": "cyclomatic_complexity_estimate",
    "call_graph_fanout_estimate_normalized": "call_graph_fanout_estimate",
    "executable_section_ratio_normalized": "executable_section_ratio",
    "readonly_section_ratio_normalized": "readonly_section_ratio",
    "writable_section_ratio_normalized": "writable_section_ratio",
}
# Every "<label>_constant_count_normalized" / "<label>_constant_count" pair
# (one per crypto magic constant in analysis/constants.py) follows the
# same pattern and is added programmatically in `_normalized_source_key_for`.

# Raw feature-vector keys that feed a "*_encoded" training column, for
# the (now rare, post-leakage-removal) case a retrain still selects one.
# `architecture` is a real property of the binary's content, not
# dataset provenance, so it is treated as legitimately derivable rather
# than "not applicable" the way project/compiler/etc. were in Phase 5B.
_ENCODED_SOURCE_KEYS: dict[str, str] = {"architecture_encoded": "architecture"}

# Dataset-provenance-only fields that never apply to a runtime firmware
# sample (kept for robustness in case a future retrain reintroduces one
# of these into the selected feature set despite the Phase 6 leakage fix).
_DATASET_PROVENANCE_ONLY_KEYS: set[str] = {
    "project", "compiler", "compiler_version", "build_type",
    "build_system", "crypto_library", "binary_type",
}

# Boolean crypto-evidence / curve-detection feature columns used
# directly (0/1) -- covers both the original Phase 4 flags and the
# Phase 6 additions (ECC curve OIDs, RSA exponent, known-library flag).
_BOOLEAN_FEATURE_KEYS: tuple[str, ...] = (
    "aes_constant", "sha_constant", "sha1_constant", "md5_constant",
    "rsa_symbol", "ecc_symbol", "aes_symbol", "sha_symbol",
    "des_symbol", "chacha_symbol", "rsa_exponent_present",
    "known_crypto_library", "ecc_curve_p_256", "ecc_curve_p_384",
    "ecc_curve_p_521", "ecc_curve_secp256k1",
)

_UNKNOWN_CATEGORY_CODE = -1


def _normalized_source_key_for(column: str) -> Optional[str]:
    """Resolve a `*_normalized` training column to its raw source field.

    Handles both the explicit `_NORMALIZED_SOURCE_KEYS` table and the
    programmatic `<label>_constant_count_normalized` pattern used for
    every crypto magic-constant occurrence count.
    """
    if column in _NORMALIZED_SOURCE_KEYS:
        return _NORMALIZED_SOURCE_KEYS[column]
    if column.endswith("_constant_count_normalized"):
        return column[: -len("_normalized")]
    return None


class PredictionValidationError(ValueError):
    """Raised when a runtime feature vector cannot be validated for inference.

    Carries a human-readable message safe to return to an API caller.
    """


class ModelLoadError(RuntimeError):
    """Raised when the trained model or its supporting artifacts can't be loaded."""


@dataclass
class PredictionResult:
    """A single binary's hierarchical prediction, ready to serialize."""

    binary_name: str
    algorithm_family: str
    algorithm: str
    confidence: float
    model: str
    model_version: str
    prediction_time_ms: float
    feature_count_used: int
    prediction_timestamp: str
    family_confidence: float = 0.0
    top_contributing_features: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ModelBundle:
    """Every artifact needed for hierarchical inference, loaded once and reused."""

    family_model: Any
    algorithm_submodels: dict[str, Any]
    family_encoder: Any
    algorithm_encoder: Any
    feature_columns: list[str]
    metadata: dict[str, Any]
    categorical_encodings: dict[str, dict[str, int]]
    numeric_scaler_params: dict[str, dict[str, float]]


# --------------------------------------------------------------------------
# Loading model artifacts (once per process)
# --------------------------------------------------------------------------

def _load_json(path: Path, description: str) -> dict[str, Any]:
    if not path.exists():
        message = f"Required {description} not found at {path}."
        logger.error(message)
        raise ModelLoadError(message)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        message = f"Could not read/parse {description} at {path}: {exc}"
        logger.error(message)
        raise ModelLoadError(message) from exc


def _load_joblib(path: Path, description: str) -> Any:
    if not path.exists():
        message = f"Required {description} not found at {path}."
        logger.error(message)
        raise ModelLoadError(message)
    try:
        return joblib.load(path)
    except Exception as exc:  # noqa: BLE001 - joblib/pickle can raise many error types
        message = f"Could not load {description} from {path} (corrupted model file?): {exc}"
        logger.error(message)
        raise ModelLoadError(message) from exc


@lru_cache(maxsize=1)
def get_model_bundle() -> ModelBundle:
    """Load `best_model.pkl` and every supporting artifact, once per process.

    Raises:
        ModelLoadError: if any required artifact is missing, corrupted,
            or malformed (e.g. `best_model.pkl` isn't the expected
            `{"family_model": ..., "algorithm_submodels": ...}` shape).
    """
    models_dir = settings.ML_SAVED_MODELS_DIR
    processed_dir = settings.DATASET_PROCESSED_DIR

    logger.info("Loading hierarchical model artifacts from %s", models_dir)

    model_path = models_dir / "best_model.pkl"
    if not model_path.exists():
        model_path = models_dir / "model_v1.pkl"  # Phase 5B naming, kept for compatibility

    bundle_payload = _load_joblib(model_path, "trained model (best_model.pkl)")
    if not isinstance(bundle_payload, dict) or "family_model" not in bundle_payload:
        message = f"{model_path} is not a valid hierarchical model bundle."
        logger.error(message)
        raise ModelLoadError(message)

    family_encoder = _load_joblib(models_dir / "label_encoder.pkl", "family label encoder (label_encoder.pkl)")
    algorithm_encoder = _load_joblib(
        models_dir / "algorithm_label_encoder.pkl", "algorithm label encoder (algorithm_label_encoder.pkl)"
    )
    feature_columns = _load_json(models_dir / "feature_columns.json", "feature column list (feature_columns.json)")
    metadata = _load_json(models_dir / "metadata.json", "model metadata (metadata.json)")

    if not isinstance(feature_columns, list) or not feature_columns:
        message = f"feature_columns.json at {models_dir} is empty or malformed."
        logger.error(message)
        raise ModelLoadError(message)

    preprocessing_metadata_path = processed_dir / "preprocessing_metadata.json"
    if preprocessing_metadata_path.exists():
        preprocessing_metadata = _load_json(preprocessing_metadata_path, "dataset preprocessing metadata")
    else:
        logger.warning(
            "preprocessing_metadata.json not found at %s; categorical/numeric "
            "features will fall back to defaults instead of trained encodings.",
            preprocessing_metadata_path,
        )
        preprocessing_metadata = {}

    logger.info(
        "Model artifacts loaded: model_version=%s, feature_count=%d, families=%d, algorithms=%d",
        metadata.get("model_version", "unknown"), len(feature_columns),
        len(family_encoder.classes_), len(algorithm_encoder.classes_),
    )

    return ModelBundle(
        family_model=bundle_payload["family_model"],
        algorithm_submodels=bundle_payload.get("algorithm_submodels", {}),
        family_encoder=family_encoder,
        algorithm_encoder=algorithm_encoder,
        feature_columns=feature_columns,
        metadata=metadata,
        categorical_encodings=preprocessing_metadata.get("categorical_encodings", {}),
        numeric_scaler_params=preprocessing_metadata.get("numeric_scaler_params", {}),
    )


def reset_model_bundle_cache() -> None:
    """Clear the cached model bundle, forcing the next call to reload from disk."""
    get_model_bundle.cache_clear()


# --------------------------------------------------------------------------
# Feature validation and derivation
# --------------------------------------------------------------------------

def _encode_categorical(raw_value: Any, encoding_map: dict[str, int]) -> int:
    if raw_value is None:
        return _UNKNOWN_CATEGORY_CODE
    return encoding_map.get(str(raw_value), _UNKNOWN_CATEGORY_CODE)


def _normalize_numeric(raw_key: str, raw_value: Any, scaler_params: dict[str, float]) -> float:
    if raw_value is None:
        return 0.0
    if raw_key == "import_libraries" and isinstance(raw_value, (list, tuple)):
        raw_value = len(raw_value)
    try:
        numeric_value = float(raw_value)
    except (TypeError, ValueError):
        return 0.0
    minimum = scaler_params.get("min", 0.0)
    maximum = scaler_params.get("max", 0.0)
    value_range = maximum - minimum
    if value_range == 0:
        return 0.0
    return max(0.0, min(1.0, (numeric_value - minimum) / value_range))


def validate_and_prepare_features(
    raw_features: dict[str, Any],
    bundle: Optional[ModelBundle] = None,
) -> pd.DataFrame:
    """Validate a runtime feature vector and derive the model's exact input schema.

    See `ml/predict.py`'s Phase 5B docstring history for the full
    rationale; Phase 6's leakage-free feature set greatly simplifies
    this in practice (most selected features are now boolean crypto
    flags and normalized binary-content metrics with no dataset
    provenance to fabricate), but the same general derivation/validation
    logic is kept for robustness against future retrains.

    Raises:
        PredictionValidationError: if `raw_features` is empty/invalid,
            or a genuinely required raw feature is missing.
    """
    bundle = bundle or get_model_bundle()

    if not isinstance(raw_features, dict) or not raw_features:
        message = "Feature vector is empty or not a valid JSON object."
        logger.error(message)
        raise PredictionValidationError(message)

    missing_raw_keys: list[str] = []
    row: dict[str, float] = {}
    used_raw_keys: set[str] = set()

    for column in bundle.feature_columns:
        if column in _BOOLEAN_FEATURE_KEYS:
            if column not in raw_features:
                missing_raw_keys.append(column)
                continue
            row[column] = 1 if bool(raw_features.get(column)) else 0
            used_raw_keys.add(column)

        elif column.endswith("_was_missing"):
            row[column] = 0

        elif column.endswith("_normalized"):
            source_key = _normalized_source_key_for(column)
            if source_key is None or source_key not in raw_features:
                missing_raw_keys.append(source_key or column)
                continue
            scaler_params = bundle.numeric_scaler_params.get(source_key, {})
            row[column] = _normalize_numeric(source_key, raw_features.get(source_key), scaler_params)
            used_raw_keys.add(source_key)

        elif column in _ENCODED_SOURCE_KEYS:
            source_key = _ENCODED_SOURCE_KEYS[column]
            if source_key in _DATASET_PROVENANCE_ONLY_KEYS:
                row[column] = _UNKNOWN_CATEGORY_CODE
            else:
                encoding_map = bundle.categorical_encodings.get(source_key, {})
                row[column] = _encode_categorical(raw_features.get(source_key), encoding_map)
                used_raw_keys.add(source_key)

        else:
            logger.debug("No derivation rule for feature column '%s'; defaulting to 0.", column)
            row[column] = 0

    if missing_raw_keys:
        message = (
            "Feature vector is missing required fields: "
            f"{sorted(set(missing_raw_keys))}. Ensure the firmware was fully "
            "analyzed by the Firmware Analysis Engine before requesting a prediction."
        )
        logger.error(message)
        raise PredictionValidationError(message)

    extra_keys = set(raw_features.keys()) - used_raw_keys
    if extra_keys:
        logger.info("Ignoring %d extra feature-vector field(s) not used by the model: %s", len(extra_keys), sorted(extra_keys))

    dataframe = pd.DataFrame([row])[bundle.feature_columns]
    return dataframe


# --------------------------------------------------------------------------
# Per-prediction SHAP explanation
# --------------------------------------------------------------------------

def _explain_prediction(bundle: ModelBundle, prepared_row: pd.DataFrame) -> list[dict[str, Any]]:
    """Rank features by |SHAP value| for one specific prediction.

    Uses the family-level model (the single global model in the
    hierarchy) as the explainer target. Never raises -- returns an
    empty list if SHAP is unavailable or explanation fails, since this
    is supplementary information, not required for the prediction itself.
    """
    if shap is None:
        return []
    try:
        explainer = shap.TreeExplainer(bundle.family_model)
        shap_values = explainer.shap_values(prepared_row)
        values_array = np.asarray(shap_values)
        if values_array.ndim == 3:
            row_values = np.abs(values_array[0]).mean(axis=1)
        elif isinstance(shap_values, list):
            row_values = np.mean([np.abs(v[0]) for v in shap_values], axis=0)
        else:
            row_values = np.abs(values_array[0])

        ranking = sorted(
            zip(prepared_row.columns, row_values.tolist()), key=lambda pair: pair[1], reverse=True
        )
        return [{"feature": name, "abs_shap": round(value, 6)} for name, value in ranking[:5]]
    except Exception as exc:  # noqa: BLE001
        logger.debug("Per-prediction SHAP explanation unavailable: %s", exc)
        return []


# --------------------------------------------------------------------------
# Prediction
# --------------------------------------------------------------------------

def predict_single(
    raw_features: dict[str, Any],
    binary_name: str = "unknown",
    explain: bool = False,
) -> PredictionResult:
    """Run hierarchical (family -> algorithm) inference for one binary.

    Raises:
        PredictionValidationError: if the feature vector fails validation.
        ModelLoadError: if the model artifacts could not be loaded.
    """
    bundle = get_model_bundle()

    logger.info("Prediction started: binary_name=%s", binary_name)
    prepared = validate_and_prepare_features(raw_features, bundle)

    start_time = time.perf_counter()
    try:
        family_index = int(bundle.family_model.predict(prepared)[0])
        family_probabilities = bundle.family_model.predict_proba(prepared)[0]
        family = str(bundle.family_encoder.inverse_transform([family_index])[0])
        family_confidence = float(round(max(family_probabilities) * 100, 2))

        submodel = bundle.algorithm_submodels.get(family)
        if submodel is None:
            message = f"No algorithm sub-model is available for the predicted family '{family}'."
            logger.error(message)
            raise RuntimeError(message)

        algorithm_index = int(submodel.predict(prepared)[0])
        algorithm_probabilities = submodel.predict_proba(prepared)[0]
        algorithm = str(bundle.algorithm_encoder.inverse_transform([algorithm_index])[0])
        confidence = float(round(max(algorithm_probabilities) * 100, 2))
    except RuntimeError:
        raise
    except Exception as exc:  # noqa: BLE001
        message = f"Model inference failed for binary '{binary_name}': {exc}"
        logger.error(message)
        raise RuntimeError(message) from exc

    prediction_time_ms = round((time.perf_counter() - start_time) * 1000, 3)

    top_features = _explain_prediction(bundle, prepared) if explain else []

    logger.info(
        "Prediction completed: binary_name=%s, family=%s, algorithm=%s, confidence=%.2f%%, time=%.3fms",
        binary_name, family, algorithm, confidence, prediction_time_ms,
    )

    return PredictionResult(
        binary_name=binary_name,
        algorithm_family=family,
        algorithm=algorithm,
        confidence=confidence,
        model=str(bundle.metadata.get("winning_model", "unknown")),
        model_version=str(bundle.metadata.get("model_version", "unknown")),
        prediction_time_ms=prediction_time_ms,
        feature_count_used=len(bundle.feature_columns),
        prediction_timestamp=datetime.now(timezone.utc).isoformat(),
        family_confidence=family_confidence,
        top_contributing_features=top_features,
    )


def predict_batch(
    feature_vectors: list[tuple[str, dict[str, Any]]],
    explain: bool = False,
) -> tuple[list[PredictionResult], list[dict[str, str]]]:
    """Run hierarchical inference for multiple binaries.

    A single binary's validation or inference failure never stops the
    rest of the batch -- it is logged and recorded in the returned
    failure list instead.

    Args:
        feature_vectors: list of (binary_name, raw_feature_dict) pairs.

    Returns:
        A tuple of (successful `PredictionResult`s, failures).
    """
    results: list[PredictionResult] = []
    failures: list[dict[str, str]] = []

    for binary_name, raw_features in feature_vectors:
        try:
            results.append(predict_single(raw_features, binary_name, explain=explain))
        except (PredictionValidationError, RuntimeError, ModelLoadError) as exc:
            logger.error("Skipping binary '%s' due to prediction failure: %s", binary_name, exc)
            failures.append({"binary_name": binary_name, "error": str(exc)})

    return results, failures


# --------------------------------------------------------------------------
# Locating feature vectors for a given firmware
# --------------------------------------------------------------------------

def load_feature_vectors_for_firmware(
    firmware_id: int,
    analysis_output_dir: Optional[Path] = None,
) -> list[tuple[str, dict[str, Any]]]:
    """Find and load every `*_feature_vector.json` produced for a firmware.

    Looks under `<analysis_output_dir>/<firmware_id>/` (recursively).
    Never raises for an individual unreadable file -- it is logged and
    skipped.
    """
    analysis_output_dir = analysis_output_dir or settings.ANALYSIS_OUTPUT_DIR
    firmware_dir = Path(analysis_output_dir) / str(firmware_id)

    if not firmware_dir.exists():
        logger.warning("No analysis output directory found for firmware_id=%s at %s", firmware_id, firmware_dir)
        return []

    feature_vector_paths = sorted(firmware_dir.rglob("*_feature_vector.json"))
    logger.info("Found %d feature vector file(s) for firmware_id=%s", len(feature_vector_paths), firmware_id)

    results: list[tuple[str, dict[str, Any]]] = []
    for path in feature_vector_paths:
        try:
            raw_features = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not read feature vector %s: %s", path, exc)
            continue

        binary_name = raw_features.get("binary_name") or path.name.removesuffix("_feature_vector.json")
        results.append((binary_name, raw_features))

    return results
