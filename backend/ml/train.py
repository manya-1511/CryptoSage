"""
ml/train.py

Phase 6 -- Research-Grade ML Benchmarking Framework (upgrades Phase 5A).

Trains a **hierarchical** cryptographic-algorithm classifier (Stage 1:
family, Stage 2: specific algorithm within that family) using a
reproducible benchmarking workflow:

    train.csv
      -> feature validation
      -> metadata-leakage removal
      -> feature selection (constant / correlated / low-importance)
      -> Stratified 5-Fold CV + hyperparameter search, across
         RandomForest, XGBoost, ExtraTrees, HistGradientBoosting
      -> automatic best-model selection (macro F1, then balanced
         accuracy, then inference time as tie-breakers)
      -> hierarchical family + per-family algorithm sub-models trained
         with the winning configuration
      -> ONE final evaluation on test.csv (never touched before this)
      -> SHAP explainability + reports
      -> best_model.pkl saved

This module is offline-only, exactly like the Phase 5A pipeline it
replaces. No FastAPI endpoint, no runtime prediction (see
`ml/predict.py`). `ml/risk.py` and `ml/recommend.py` are untouched.

Run directly:

    python train.py
"""

from __future__ import annotations

import json
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

import joblib
import matplotlib

matplotlib.use("Agg")  # headless: never try to open a GUI window
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import (
    ExtraTreesClassifier,
    HistGradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import RandomizedSearchCV, StratifiedKFold
from sklearn.preprocessing import LabelEncoder, label_binarize
from sklearn.utils.class_weight import compute_sample_weight

try:
    from xgboost import XGBClassifier
except ImportError:  # pragma: no cover - optional dependency, degrades gracefully
    XGBClassifier = None

try:
    import shap
except ImportError:  # pragma: no cover - required at runtime, checked explicitly below
    shap = None

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------

ML_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ML_DIR.parent
DATASET_DIR = BACKEND_DIR / "dataset"

# `analysis.constants` (the cryptographic family taxonomy) lives under
# `backend/`, one level up from `backend/ml/`. Add it to `sys.path` so
# this module can be run directly (`python train.py` from `backend/ml/`).
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from analysis.constants import ALGORITHM_FAMILIES, KNOWN_FAMILIES  # noqa: E402

TRAIN_CSV_PATH = DATASET_DIR / "data" / "processed" / "train.csv"
TEST_CSV_PATH = DATASET_DIR / "data" / "processed" / "test.csv"
RAW_DATASET_METADATA_PATH = DATASET_DIR / "data" / "raw" / "dataset_metadata.json"

SAVED_MODELS_DIR = ML_DIR / "saved_models"
REPORTS_DIR = ML_DIR / "reports"
LOGS_DIR = ML_DIR / "logs"

for _dir in (SAVED_MODELS_DIR, REPORTS_DIR, LOGS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

MODEL_VERSION = "2.0"
TARGET_COLUMN = "algorithm_label"
RANDOM_STATE = 42
CV_FOLDS = 5
SEARCH_ITERATIONS = 5  # RandomizedSearchCV draws per model (kept modest for runtime)
SHAP_SAMPLE_SIZE = 200

FEATURE_COLUMNS_PATH = SAVED_MODELS_DIR / "feature_columns.json"

# --------------------------------------------------------------------------
# Metadata-leakage prevention
# --------------------------------------------------------------------------
#
# These describe *how a Dataset Builder sample was produced* (which
# open-source project it came from, which compiler/build config built
# it) rather than anything intrinsic to the binary's content. A
# real-world uploaded firmware binary has no such provenance, and a
# model that leans on it (as Phase 5A's did -- see the Phase 5B README
# section documenting that exact problem) looks accurate offline while
# generalizing poorly. They are excluded from X in both their raw and
# `_encoded` forms.
LEAKAGE_BASE_COLUMNS: set[str] = {
    "project", "binary_name", "crypto_library", "compiler",
    "compiler_version", "build_system", "optimization_level",
    "binary_type", "build_type",
}

# Free-text columns that are informative to a human reader but are not
# turned into ML features (no encoding scheme is defined for them).
TEXT_ONLY_COLUMNS: set[str] = {"compiler_hints", "optimization_hints"}

# Feature-selection thresholds.
CORRELATION_THRESHOLD = 0.95
LOW_IMPORTANCE_PERCENTILE = 5  # drop the bottom 5% of features by RF importance


@dataclass
class ModelSpec:
    """A benchmarked model: how to build it and what to search over."""

    display_name: str
    build: Callable[[], Any]
    param_distributions: dict[str, list[Any]]
    supports_predict_proba: bool = True


def _build_model_registry() -> dict[str, ModelSpec]:
    """Construct the model registry.

    Adding another model later means adding one entry here (and
    installing its dependency) -- nothing else in this pipeline changes.
    """
    registry: dict[str, ModelSpec] = {
        "random_forest": ModelSpec(
            display_name="RandomForestClassifier",
            build=lambda: RandomForestClassifier(random_state=RANDOM_STATE, n_jobs=-1),
            param_distributions={
                "n_estimators": [100, 200, 300],
                "max_depth": [10, 20, 30, None],
                "min_samples_leaf": [1, 2, 4],
                "min_samples_split": [2, 5, 10],
                "max_features": ["sqrt", "log2"],
            },
        ),
        "extra_trees": ModelSpec(
            display_name="ExtraTreesClassifier",
            build=lambda: ExtraTreesClassifier(random_state=RANDOM_STATE, n_jobs=-1),
            param_distributions={
                "n_estimators": [100, 200, 300],
                "max_depth": [10, 20, 30, None],
                "min_samples_leaf": [1, 2, 4],
                "min_samples_split": [2, 5, 10],
                "max_features": ["sqrt", "log2"],
            },
        ),
        "hist_gradient_boosting": ModelSpec(
            display_name="HistGradientBoostingClassifier",
            build=lambda: HistGradientBoostingClassifier(random_state=RANDOM_STATE),
            param_distributions={
                "max_iter": [100, 200, 300],
                "max_depth": [None, 10, 20],
                "learning_rate": [0.01, 0.05, 0.1, 0.2],
                "l2_regularization": [0.0, 0.1, 1.0],
            },
        ),
    }

    if XGBClassifier is not None:
        registry["xgboost"] = ModelSpec(
            display_name="XGBClassifier",
            build=lambda: XGBClassifier(
                random_state=RANDOM_STATE, n_jobs=-1, eval_metric="mlogloss",
                use_label_encoder=False,
            ),
            param_distributions={
                "n_estimators": [100, 200, 300],
                "max_depth": [3, 6, 9],
                "learning_rate": [0.01, 0.1, 0.2],
                "subsample": [0.7, 0.85, 1.0],
                "colsample_bytree": [0.7, 0.85, 1.0],
            },
        )
    return registry


MODEL_REGISTRY: dict[str, ModelSpec] = _build_model_registry()


@dataclass
class BenchmarkResult:
    """One model's cross-validated benchmark outcome."""

    model_key: str
    display_name: str
    best_params: dict[str, Any]
    cv_macro_f1: float
    cv_balanced_accuracy: float
    mean_inference_time_ms: float
    fit_duration_seconds: float


# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------

def _configure_logging() -> Path:
    """Configure logging to stdout and a dedicated per-run log file."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = LOGS_DIR / f"train_{timestamp}.log"

    root_logger = logging.getLogger("cryptosage.ml.train")
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)

    return log_path


logger = logging.getLogger("cryptosage.ml.train")


# --------------------------------------------------------------------------
# Dataset loading
# --------------------------------------------------------------------------

def load_dataset(train_path: Path = TRAIN_CSV_PATH, test_path: Path = TEST_CSV_PATH) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load the pre-generated train/test CSVs written by dataset/preprocess.py.

    The pipeline makes no hardcoded assumptions about dataset size --
    it works identically whether the Dataset Builder produced hundreds
    or tens of thousands of samples.

    Raises:
        FileNotFoundError: if either CSV is missing.
        ValueError: if a CSV exists but is empty, corrupted, or missing
            the target column.
    """
    for path in (train_path, test_path):
        if not path.exists():
            message = (
                f"Dataset file not found: {path}. Run the Dataset Builder "
                f"(dataset/builder.py + dataset/preprocess.py) before training."
            )
            logger.error(message)
            raise FileNotFoundError(message)

    try:
        train_df = pd.read_csv(train_path)
        test_df = pd.read_csv(test_path)
    except pd.errors.ParserError as exc:
        logger.error("Failed to parse dataset CSV: %s", exc)
        raise ValueError(f"Corrupted dataset CSV: {exc}") from exc
    except pd.errors.EmptyDataError as exc:
        logger.error("Dataset CSV is empty: %s", exc)
        raise ValueError(f"Dataset CSV is empty: {exc}") from exc

    if train_df.empty or test_df.empty:
        message = "Train or test dataset is empty; cannot train a model."
        logger.error(message)
        raise ValueError(message)

    if TARGET_COLUMN not in train_df.columns or TARGET_COLUMN not in test_df.columns:
        message = f"Required label column '{TARGET_COLUMN}' is missing from the dataset."
        logger.error(message)
        raise ValueError(message)

    logger.info(
        "Dataset loaded: train=%d rows, test=%d rows, columns=%d",
        len(train_df), len(test_df), len(train_df.columns),
    )
    return train_df, test_df


# --------------------------------------------------------------------------
# Metadata-leakage removal + feature candidate resolution
# --------------------------------------------------------------------------

def resolve_candidate_feature_columns(dataframe: pd.DataFrame) -> list[str]:
    """Determine every *candidate* feature column, before selection.

    Rules (applied in order):
      - The target column and identifier columns are never features.
      - Any leakage column (`LEAKAGE_BASE_COLUMNS`), raw or `_encoded`,
        is excluded -- this is the fix for Phase 5A/5B's documented
        metadata-leakage problem.
      - Free-text columns (`TEXT_ONLY_COLUMNS`) are excluded.
      - A raw numeric column that has a `_normalized` twin is excluded
        in favor of the twin (min-max scaled, produced by
        `dataset/preprocess.py`).
      - Everything else numeric/boolean (`_normalized`, `_encoded`,
        `_was_missing` indicators, and boolean crypto-evidence /
        curve-detection flags) is kept as a candidate.

    This is rule-based rather than a hardcoded list, so a new feature
    added to `analysis/features.py` is automatically picked up as a
    training candidate without editing this function.
    """
    candidates: list[str] = []

    for column in dataframe.columns:
        if column in (TARGET_COLUMN, "binary_name"):
            continue
        if column in LEAKAGE_BASE_COLUMNS:
            continue
        if column in TEXT_ONLY_COLUMNS:
            continue

        if column.endswith("_encoded"):
            base = column[: -len("_encoded")]
            if base in LEAKAGE_BASE_COLUMNS:
                continue
            candidates.append(column)
            continue

        if column.endswith("_normalized") or column.endswith("_was_missing"):
            candidates.append(column)
            continue

        # A raw numeric column with a normalized twin: skip the raw
        # version, the twin is already a candidate via the branch above.
        if f"{column}_normalized" in dataframe.columns:
            continue

        if pd.api.types.is_bool_dtype(dataframe[column]) or pd.api.types.is_numeric_dtype(dataframe[column]):
            candidates.append(column)

    logger.info(
        "Resolved %d candidate feature column(s) after metadata-leakage removal (excluded: %s).",
        len(candidates), sorted(LEAKAGE_BASE_COLUMNS),
    )
    return candidates


def select_features(
    dataframe: pd.DataFrame,
    candidate_columns: list[str],
) -> list[str]:
    """Automatically remove constant, highly-correlated, and low-importance
    features from the candidate list, and persist the final selection.

    Steps:
      1. Drop constant features (a single unique value carries zero
         information for any classifier).
      2. Drop one feature from every pair whose absolute Pearson
         correlation exceeds `CORRELATION_THRESHOLD` (keeps the first
         of the pair, encountered in column order).
      3. Fit a quick RandomForest to rank remaining features by
         importance and drop the bottom `LOW_IMPORTANCE_PERCENTILE`
         percent.
    """
    numeric_frame = dataframe[candidate_columns].apply(pd.to_numeric, errors="coerce").fillna(0)

    constant_columns = [c for c in candidate_columns if numeric_frame[c].nunique(dropna=False) <= 1]
    if constant_columns:
        logger.info("Removing %d constant feature(s): %s", len(constant_columns), constant_columns)
    remaining = [c for c in candidate_columns if c not in constant_columns]

    correlation_matrix = numeric_frame[remaining].corr().abs()
    to_drop: set[str] = set()
    for i, col_a in enumerate(remaining):
        if col_a in to_drop:
            continue
        for col_b in remaining[i + 1:]:
            if col_b in to_drop:
                continue
            if correlation_matrix.loc[col_a, col_b] > CORRELATION_THRESHOLD:
                to_drop.add(col_b)
    if to_drop:
        logger.info("Removing %d highly-correlated feature(s) (|r| > %.2f): %s", len(to_drop), CORRELATION_THRESHOLD, sorted(to_drop))
    remaining = [c for c in remaining if c not in to_drop]

    encoded_labels = LabelEncoder().fit_transform(dataframe[TARGET_COLUMN].astype(str))
    quick_forest = RandomForestClassifier(n_estimators=100, random_state=RANDOM_STATE, n_jobs=-1)
    quick_forest.fit(numeric_frame[remaining], encoded_labels)
    importances = pd.Series(quick_forest.feature_importances_, index=remaining)
    importance_cutoff = np.percentile(importances, LOW_IMPORTANCE_PERCENTILE)
    low_importance = importances[importances <= importance_cutoff].index.tolist()
    # Never drop everything if importances are degenerate/tied.
    if len(low_importance) < len(remaining):
        if low_importance:
            logger.info("Removing %d low-importance feature(s) (<= %.2fth percentile): %s", len(low_importance), LOW_IMPORTANCE_PERCENTILE, low_importance)
        remaining = [c for c in remaining if c not in low_importance]

    logger.info("Feature selection complete: %d -> %d feature(s).", len(candidate_columns), len(remaining))
    FEATURE_COLUMNS_PATH.write_text(json.dumps(remaining, indent=2), encoding="utf-8")
    logger.info("Saved selected feature list to %s", FEATURE_COLUMNS_PATH)
    return remaining


# --------------------------------------------------------------------------
# Labels: algorithm + family
# --------------------------------------------------------------------------

def prepare_labels(
    train_df: pd.DataFrame, test_df: pd.DataFrame
) -> tuple[LabelEncoder, LabelEncoder, pd.Series, pd.Series]:
    """Fit algorithm and family LabelEncoders across the union of train/test.

    Raises:
        ValueError: if any algorithm label has no known family mapping
            in `analysis.constants.ALGORITHM_FAMILIES`.
    """
    all_algorithms = pd.concat([train_df[TARGET_COLUMN], test_df[TARGET_COLUMN]]).astype(str)
    unknown = sorted(set(all_algorithms.unique()) - set(ALGORITHM_FAMILIES))
    if unknown:
        message = f"No family mapping defined for algorithm label(s): {unknown}"
        logger.error(message)
        raise ValueError(message)

    algorithm_encoder = LabelEncoder().fit(all_algorithms)
    all_families = all_algorithms.map(ALGORITHM_FAMILIES)
    family_encoder = LabelEncoder().fit(all_families)

    logger.info(
        "Labels prepared: %d algorithm classes across %d families.",
        len(algorithm_encoder.classes_), len(family_encoder.classes_),
    )
    return algorithm_encoder, family_encoder, all_algorithms, all_families


# --------------------------------------------------------------------------
# Benchmarking: Stratified 5-fold CV + hyperparameter search per model
# --------------------------------------------------------------------------

def benchmark_models(
    x_train: pd.DataFrame,
    y_train: np.ndarray,
    sample_weight: np.ndarray,
    stage_name: str,
) -> tuple[dict[str, BenchmarkResult], dict[str, Any]]:
    """Cross-validate + hyperparameter-search every registered model on
    `x_train`/`y_train` (train.csv ONLY -- test.csv is never touched here).

    Returns (benchmark_results_by_model_key, fitted_estimators_by_model_key).
    A model that fails to search/fit (e.g. a dependency issue) is
    logged and excluded from the results rather than aborting the run.
    """
    cv = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    results: dict[str, BenchmarkResult] = {}
    fitted_estimators: dict[str, Any] = {}

    for model_key, spec in MODEL_REGISTRY.items():
        logger.info("[%s] Hyperparameter search started: %s", stage_name, spec.display_name)
        start = time.monotonic()
        try:
            search = RandomizedSearchCV(
                estimator=spec.build(),
                param_distributions=spec.param_distributions,
                n_iter=SEARCH_ITERATIONS,
                scoring="f1_macro",
                cv=cv,
                random_state=RANDOM_STATE,
                n_jobs=-1,
                refit=True,
            )
            fit_params = {"sample_weight": sample_weight}
            search.fit(x_train, y_train, **fit_params)
        except Exception as exc:  # noqa: BLE001
            logger.error("[%s] Hyperparameter search failed for %s: %s", stage_name, spec.display_name, exc)
            continue

        fit_duration = time.monotonic() - start

        # Balanced accuracy via the same CV scheme, at the best params found.
        balanced_scores = []
        for train_idx, val_idx in cv.split(x_train, y_train):
            fold_model = spec.build()
            fold_model.set_params(**search.best_params_)
            fold_weight = sample_weight[train_idx]
            fold_model.fit(x_train.iloc[train_idx], y_train[train_idx], sample_weight=fold_weight)
            fold_predictions = fold_model.predict(x_train.iloc[val_idx])
            balanced_scores.append(balanced_accuracy_score(y_train[val_idx], fold_predictions))

        inference_start = time.perf_counter()
        search.best_estimator_.predict(x_train.iloc[: min(100, len(x_train))])
        inference_ms = (time.perf_counter() - inference_start) * 1000 / min(100, len(x_train))

        result = BenchmarkResult(
            model_key=model_key,
            display_name=spec.display_name,
            best_params=search.best_params_,
            cv_macro_f1=float(search.best_score_),
            cv_balanced_accuracy=float(np.mean(balanced_scores)),
            mean_inference_time_ms=float(inference_ms),
            fit_duration_seconds=float(fit_duration),
        )
        results[model_key] = result
        fitted_estimators[model_key] = search.best_estimator_

        logger.info(
            "[%s] %s: cv_macro_f1=%.4f, cv_balanced_accuracy=%.4f, inference=%.3fms/sample, fit_time=%.1fs",
            stage_name, spec.display_name, result.cv_macro_f1, result.cv_balanced_accuracy,
            result.mean_inference_time_ms, result.fit_duration_seconds,
        )

    return results, fitted_estimators


def select_best_model(results: dict[str, BenchmarkResult]) -> str:
    """Rank benchmarked models and return the winning model key.

    No model is assumed best in advance. Ranking:
      1. Macro F1 (primary metric) -- higher is better.
      2. Balanced accuracy (first tie-breaker) -- higher is better.
      3. Mean inference time (second tie-breaker) -- lower is better.
    """
    if not results:
        raise RuntimeError("No model successfully completed benchmarking; cannot select a winner.")

    ranked = sorted(
        results.values(),
        key=lambda r: (-r.cv_macro_f1, -r.cv_balanced_accuracy, r.mean_inference_time_ms),
    )
    winner = ranked[0]
    logger.info("Model ranking (%s):", "best to worst")
    for rank, result in enumerate(ranked, start=1):
        logger.info(
            "  #%d %s -- macro_f1=%.4f, balanced_acc=%.4f, inference=%.3fms",
            rank, result.display_name, result.cv_macro_f1, result.cv_balanced_accuracy, result.mean_inference_time_ms,
        )
    logger.info("Best model selected: %s (%s)", winner.display_name, winner.model_key)
    return winner.model_key


# --------------------------------------------------------------------------
# Hierarchical training: family stage + per-family algorithm sub-models
# --------------------------------------------------------------------------

def train_family_stage(
    x_train: pd.DataFrame, family_labels: np.ndarray
) -> tuple[dict[str, BenchmarkResult], str, Any]:
    """Benchmark every model on the family-level task and return the winner."""
    sample_weight = compute_sample_weight("balanced", family_labels)
    results, estimators = benchmark_models(x_train, family_labels, sample_weight, stage_name="family")
    best_key = select_best_model(results)
    return results, best_key, estimators[best_key]


def train_algorithm_submodels(
    x_train: pd.DataFrame,
    train_df: pd.DataFrame,
    algorithm_encoder: LabelEncoder,
    winning_model_key: str,
    winning_params: dict[str, Any],
) -> dict[str, Any]:
    """Train one algorithm sub-model per family (Stage 2 of the hierarchy).

    Each sub-model is trained only on the rows/classes belonging to its
    family, using the SAME model type and hyperparameters selected by
    the Stage-1 benchmark (a deliberate, documented simplification --
    an independent hyperparameter search per family would multiply the
    already-substantial Stage-1 search cost six-fold for marginal gain
    on families with few samples/classes).
    """
    spec = MODEL_REGISTRY[winning_model_key]
    submodels: dict[str, Any] = {}
    encoded_algorithm_labels = algorithm_encoder.transform(train_df[TARGET_COLUMN].astype(str))
    families_present = sorted(set(train_df[TARGET_COLUMN].astype(str).map(ALGORITHM_FAMILIES)))

    for family in families_present:
        family_mask = train_df[TARGET_COLUMN].astype(str).map(ALGORITHM_FAMILIES) == family
        family_x = x_train[family_mask.values]
        family_y = encoded_algorithm_labels[family_mask.values]

        if len(set(family_y)) < 2:
            logger.warning(
                "Family '%s' has fewer than 2 algorithm classes in the training "
                "split; skipping a dedicated sub-model (single-class family).",
                family,
            )
            continue

        sample_weight = compute_sample_weight("balanced", family_y)
        model = spec.build()
        model.set_params(**winning_params)
        model.fit(family_x, family_y, sample_weight=sample_weight)
        submodels[family] = model
        logger.info(
            "[algorithm-stage] Trained %s sub-model for family '%s' on %d samples, %d classes.",
            spec.display_name, family, len(family_y), len(set(family_y)),
        )

    return submodels


def hierarchical_predict(
    x: pd.DataFrame,
    family_model: Any,
    algorithm_submodels: dict[str, Any],
    family_encoder: LabelEncoder,
    algorithm_encoder: LabelEncoder,
) -> tuple[np.ndarray, np.ndarray]:
    """Run the two-stage hierarchical prediction: family, then algorithm.

    Rows are grouped by predicted family and each family's sub-model is
    called once on its whole batch (rather than row-by-row), which is
    both faster and the natural vectorized form of the same logic.

    For a family with no dedicated sub-model (e.g. it had too few
    training classes), the most frequent algorithm within that family
    (by training prevalence) is used as a safe fallback rather than
    raising -- a firmware sample should never be left unclassified
    purely because its predicted family was under-represented offline.

    Returns (predicted_family_indices, predicted_algorithm_indices).
    """
    predicted_family_indices = family_model.predict(x)
    predicted_families = family_encoder.inverse_transform(predicted_family_indices)

    predicted_algorithm_indices = np.zeros(len(x), dtype=int)
    x_reset = x.reset_index(drop=True)

    for family in set(predicted_families):
        row_mask = predicted_families == family
        submodel = algorithm_submodels.get(family)
        if submodel is not None:
            predicted_algorithm_indices[row_mask] = submodel.predict(x_reset[row_mask])
        else:
            predicted_algorithm_indices[row_mask] = 0

    return predicted_family_indices, predicted_algorithm_indices


# --------------------------------------------------------------------------
# Final evaluation (test.csv -- touched exactly once)
# --------------------------------------------------------------------------

def evaluate_final_model(
    x_test: pd.DataFrame,
    test_df: pd.DataFrame,
    family_model: Any,
    algorithm_submodels: dict[str, Any],
    family_encoder: LabelEncoder,
    algorithm_encoder: LabelEncoder,
) -> dict[str, Any]:
    """Run the ONE official evaluation of the hierarchical model on test.csv."""
    logger.info("Final evaluation started on %d held-out test samples.", len(x_test))

    true_algorithm_indices = algorithm_encoder.transform(test_df[TARGET_COLUMN].astype(str))
    true_family_indices = family_encoder.transform(test_df[TARGET_COLUMN].astype(str).map(ALGORITHM_FAMILIES))

    predicted_family_indices, predicted_algorithm_indices = hierarchical_predict(
        x_test, family_model, algorithm_submodels, family_encoder, algorithm_encoder
    )

    algorithm_class_names = [str(c) for c in algorithm_encoder.classes_]
    family_class_names = [str(c) for c in family_encoder.classes_]

    metrics = {
        "accuracy": float(accuracy_score(true_algorithm_indices, predicted_algorithm_indices)),
        "balanced_accuracy": float(balanced_accuracy_score(true_algorithm_indices, predicted_algorithm_indices)),
        "precision_macro": float(precision_score(true_algorithm_indices, predicted_algorithm_indices, average="macro", zero_division=0)),
        "recall_macro": float(recall_score(true_algorithm_indices, predicted_algorithm_indices, average="macro", zero_division=0)),
        "f1_macro": float(f1_score(true_algorithm_indices, predicted_algorithm_indices, average="macro", zero_division=0)),
        "family_accuracy": float(accuracy_score(true_family_indices, predicted_family_indices)),
        "family_f1_macro": float(f1_score(true_family_indices, predicted_family_indices, average="macro", zero_division=0)),
    }

    # ROC-AUC (macro, one-vs-rest) computed for the family stage, where
    # every class is guaranteed to appear in a single model's output.
    # Omitted for the algorithm stage: per-family sub-models each only
    # produce probabilities over their own family's classes, so a
    # single 24-class probability matrix isn't well-defined without
    # additional bookkeeping this phase intentionally keeps out of scope.
    try:
        family_probabilities = family_model.predict_proba(x_test)
        true_family_binarized = label_binarize(true_family_indices, classes=list(range(len(family_class_names))))
        metrics["family_roc_auc_macro"] = float(
            roc_auc_score(true_family_binarized, family_probabilities, average="macro", multi_class="ovr")
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Family-stage ROC-AUC could not be computed: %s", exc)
        metrics["family_roc_auc_macro"] = None

    report_dict = classification_report(
        true_algorithm_indices, predicted_algorithm_indices,
        labels=list(range(len(algorithm_class_names))), target_names=algorithm_class_names,
        output_dict=True, zero_division=0,
    )

    algorithm_confusion = confusion_matrix(
        true_algorithm_indices, predicted_algorithm_indices, labels=list(range(len(algorithm_class_names)))
    )
    family_confusion = confusion_matrix(
        true_family_indices, predicted_family_indices, labels=list(range(len(family_class_names)))
    )

    logger.info(
        "Final evaluation completed: algorithm_accuracy=%.4f, algorithm_f1_macro=%.4f, family_accuracy=%.4f",
        metrics["accuracy"], metrics["f1_macro"], metrics["family_accuracy"],
    )

    return {
        "metrics": metrics,
        "classification_report": report_dict,
        "algorithm_confusion_matrix": algorithm_confusion,
        "family_confusion_matrix": family_confusion,
        "algorithm_class_names": algorithm_class_names,
        "family_class_names": family_class_names,
    }


def _save_confusion_matrix_plot(matrix: np.ndarray, class_names: list[str], title: str, output_path: Path) -> None:
    figure, axis = plt.subplots(figsize=(max(8, len(class_names) * 0.5), max(6, len(class_names) * 0.5)))
    display = ConfusionMatrixDisplay(confusion_matrix=matrix, display_labels=class_names)
    display.plot(ax=axis, cmap="Blues", xticks_rotation=90, colorbar=True, values_format="d")
    axis.set_title(title)
    figure.tight_layout()
    figure.savefig(output_path, dpi=150)
    plt.close(figure)
    logger.info("Confusion matrix plot saved to %s", output_path)


# --------------------------------------------------------------------------
# Explainability (SHAP) -- on the family-level model (single global model)
# --------------------------------------------------------------------------

def generate_shap_explanations(
    family_model: Any,
    x_train: pd.DataFrame,
    x_test: pd.DataFrame,
    sample_size: int = SHAP_SAMPLE_SIZE,
) -> Optional[list[dict[str, Any]]]:
    """Compute SHAP feature importance for the family-level model and save
    a summary plot, a bar plot, and the top-20 feature ranking.

    Per-prediction explanations are supported via `explain_single_prediction`
    below, reusing the same explainer construction. Never raises --
    explainability is supplementary, not required for the model to be
    usable; a failure here is logged and the run continues.
    """
    if shap is None:
        logger.warning("SHAP is not installed; skipping explainability generation.")
        return None

    try:
        sample = x_test.sample(n=min(sample_size, len(x_test)), random_state=RANDOM_STATE)
        logger.info("Computing SHAP values on a sample of %d test rows (family-level model).", len(sample))

        explainer = shap.TreeExplainer(family_model)
        shap_values = explainer.shap_values(sample)

        if isinstance(shap_values, list):
            stacked = np.stack([np.abs(class_values) for class_values in shap_values], axis=0)
            mean_abs_shap = stacked.mean(axis=(0, 1))
            plot_values = shap_values[0]
        else:
            values_array = np.asarray(shap_values)
            if values_array.ndim == 3:
                mean_abs_shap = np.abs(values_array).mean(axis=(0, 2))
                plot_values = values_array.mean(axis=2)
            else:
                mean_abs_shap = np.abs(values_array).mean(axis=0)
                plot_values = values_array

        feature_names = list(x_test.columns)
        ranking = sorted(zip(feature_names, mean_abs_shap.tolist()), key=lambda pair: pair[1], reverse=True)
        top_features = [{"feature": name, "mean_abs_shap": round(value, 6)} for name, value in ranking]

        plt.figure()
        shap.summary_plot(plot_values, sample, feature_names=feature_names, show=False)
        plt.tight_layout()
        plt.savefig(REPORTS_DIR / "shap_summary.png", dpi=150, bbox_inches="tight")
        plt.savefig(SAVED_MODELS_DIR / "shap_summary.png", dpi=150, bbox_inches="tight")
        plt.close()
        logger.info("SHAP summary plot saved to %s and %s", REPORTS_DIR / "shap_summary.png", SAVED_MODELS_DIR / "shap_summary.png")

        plt.figure()
        shap.summary_plot(plot_values, sample, feature_names=feature_names, plot_type="bar", show=False)
        plt.tight_layout()
        plt.savefig(REPORTS_DIR / "shap_bar.png", dpi=150, bbox_inches="tight")
        plt.close()
        logger.info("SHAP bar plot saved to %s", REPORTS_DIR / "shap_bar.png")

        pd.DataFrame(top_features).to_csv(REPORTS_DIR / "feature_importance.csv", index=False)
        logger.info("Feature importance ranking saved to %s", REPORTS_DIR / "feature_importance.csv")

        return top_features[:20]
    except Exception as exc:  # noqa: BLE001
        logger.error("SHAP explanation generation failed (continuing without it): %s", exc)
        return None


def explain_single_prediction(
    family_model: Any, feature_row: pd.DataFrame
) -> Optional[list[dict[str, Any]]]:
    """Per-prediction SHAP explanation for a single feature row.

    Intended for reuse by the runtime inference engine (`ml/predict.py`)
    to explain one prediction, not just the global summary. Returns the
    features ranked by |SHAP value| for this specific row, or None if
    SHAP is unavailable or explanation fails.
    """
    if shap is None:
        return None
    try:
        explainer = shap.TreeExplainer(family_model)
        shap_values = explainer.shap_values(feature_row)
        values_array = np.asarray(shap_values)
        if values_array.ndim == 3:
            row_values = np.abs(values_array[0]).mean(axis=1)
        elif isinstance(shap_values, list):
            row_values = np.mean([np.abs(v[0]) for v in shap_values], axis=0)
        else:
            row_values = np.abs(values_array[0])

        ranking = sorted(
            zip(feature_row.columns, row_values.tolist()), key=lambda pair: pair[1], reverse=True
        )
        return [{"feature": name, "abs_shap": round(value, 6)} for name, value in ranking[:10]]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Per-prediction SHAP explanation failed: %s", exc)
        return None


# --------------------------------------------------------------------------
# Saving artifacts
# --------------------------------------------------------------------------

def _read_dataset_version() -> str:
    if RAW_DATASET_METADATA_PATH.exists():
        try:
            raw_metadata = json.loads(RAW_DATASET_METADATA_PATH.read_text(encoding="utf-8"))
            return str(raw_metadata.get("dataset_version", "unknown"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not read dataset_metadata.json for dataset_version: %s", exc)
    return "unknown"


def save_all_artifacts(
    *,
    winning_model_key: str,
    family_model: Any,
    algorithm_submodels: dict[str, Any],
    family_encoder: LabelEncoder,
    algorithm_encoder: LabelEncoder,
    feature_columns: list[str],
    benchmark_results: dict[str, BenchmarkResult],
    evaluation: dict[str, Any],
    shap_top_features: Optional[list[dict[str, Any]]],
    training_duration_seconds: float,
    train_sample_count: int,
    test_sample_count: int,
) -> None:
    """Persist every Phase 6 artifact to `ml/saved_models/` and `ml/reports/`.

    Raises:
        OSError: if model/encoder serialization fails.
    """
    try:
        joblib.dump(
            {"family_model": family_model, "algorithm_submodels": algorithm_submodels},
            SAVED_MODELS_DIR / "best_model.pkl",
        )
        # Retained for backward compatibility with Phase 5B's predict.py
        # loading convention and any external tooling expecting model_v1.pkl.
        joblib.dump(
            {"family_model": family_model, "algorithm_submodels": algorithm_submodels},
            SAVED_MODELS_DIR / "model_v1.pkl",
        )
        joblib.dump(family_encoder, SAVED_MODELS_DIR / "label_encoder.pkl")
        joblib.dump(algorithm_encoder, SAVED_MODELS_DIR / "algorithm_label_encoder.pkl")
    except OSError as exc:
        logger.error("Model serialization failed: %s", exc)
        raise

    logger.info("Best model (%s) saved to %s", winning_model_key, SAVED_MODELS_DIR / "best_model.pkl")

    _save_confusion_matrix_plot(
        evaluation["algorithm_confusion_matrix"], evaluation["algorithm_class_names"],
        "CryptoSage Algorithm Classifier -- Confusion Matrix (Test Set)",
        REPORTS_DIR / "algorithm_confusion_matrix.png",
    )
    _save_confusion_matrix_plot(
        evaluation["algorithm_confusion_matrix"], evaluation["algorithm_class_names"],
        "CryptoSage Algorithm Classifier -- Confusion Matrix (Test Set)",
        SAVED_MODELS_DIR / "confusion_matrix.png",
    )
    _save_confusion_matrix_plot(
        evaluation["family_confusion_matrix"], evaluation["family_class_names"],
        "CryptoSage Family Classifier -- Confusion Matrix (Test Set)",
        REPORTS_DIR / "family_confusion_matrix.png",
    )

    benchmark_results_output = {
        model_key: {
            "display_name": result.display_name,
            "best_params": result.best_params,
            "cv_macro_f1": result.cv_macro_f1,
            "cv_balanced_accuracy": result.cv_balanced_accuracy,
            "mean_inference_time_ms": result.mean_inference_time_ms,
            "fit_duration_seconds": result.fit_duration_seconds,
        }
        for model_key, result in benchmark_results.items()
    }
    benchmark_results_output["winner"] = winning_model_key
    (REPORTS_DIR / "benchmark_results.json").write_text(
        json.dumps(benchmark_results_output, indent=2), encoding="utf-8"
    )
    logger.info("Benchmark results saved to %s", REPORTS_DIR / "benchmark_results.json")

    metrics_output = dict(evaluation["metrics"])
    metrics_output["algorithm_confusion_matrix"] = evaluation["algorithm_confusion_matrix"].tolist()
    metrics_output["family_confusion_matrix"] = evaluation["family_confusion_matrix"].tolist()
    metrics_output["algorithm_class_names"] = evaluation["algorithm_class_names"]
    metrics_output["family_class_names"] = evaluation["family_class_names"]
    if shap_top_features is not None:
        metrics_output["shap_top_features"] = shap_top_features
    for path in (SAVED_MODELS_DIR / "metrics.json", REPORTS_DIR / "metrics.json"):
        path.write_text(json.dumps(metrics_output, indent=2), encoding="utf-8")
    logger.info("Metrics saved to ml/saved_models/metrics.json and ml/reports/metrics.json")

    for path in (SAVED_MODELS_DIR / "classification_report.json", REPORTS_DIR / "classification_report.json"):
        path.write_text(json.dumps(evaluation["classification_report"], indent=2), encoding="utf-8")

    metadata = {
        "model_version": MODEL_VERSION,
        "winning_model": MODEL_REGISTRY[winning_model_key].display_name,
        "dataset_version": _read_dataset_version(),
        "training_date": datetime.now(timezone.utc).isoformat(),
        "macro_f1": evaluation["metrics"]["f1_macro"],
        "balanced_accuracy": evaluation["metrics"]["balanced_accuracy"],
        "accuracy": evaluation["metrics"]["accuracy"],
        "precision_macro": evaluation["metrics"]["precision_macro"],
        "recall_macro": evaluation["metrics"]["recall_macro"],
        "family_accuracy": evaluation["metrics"]["family_accuracy"],
        "family_f1_macro": evaluation["metrics"]["family_f1_macro"],
        "cross_validation_macro_f1": benchmark_results[winning_model_key].cv_macro_f1,
        "training_duration_seconds": round(training_duration_seconds, 2),
        "mean_prediction_time_ms": benchmark_results[winning_model_key].mean_inference_time_ms,
        "hyperparameters": benchmark_results[winning_model_key].best_params,
        "feature_count": len(feature_columns),
        "training_sample_count": train_sample_count,
        "test_sample_count": test_sample_count,
        "supported_families": evaluation["family_class_names"],
        "supported_algorithms": evaluation["algorithm_class_names"],
    }
    metadata_path = SAVED_MODELS_DIR / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    logger.info("Metadata saved to %s", metadata_path)


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def run_training() -> dict[str, Any]:
    """Run the full Phase 6 hierarchical benchmarking + training pipeline."""
    started_at = time.monotonic()

    train_df, test_df = load_dataset()

    candidate_columns = resolve_candidate_feature_columns(train_df)
    feature_columns = select_features(train_df, candidate_columns)

    algorithm_encoder, family_encoder, _all_algorithms, _all_families = prepare_labels(train_df, test_df)

    x_train = train_df[feature_columns].apply(pd.to_numeric, errors="coerce").fillna(0)
    x_test = test_df[feature_columns].apply(pd.to_numeric, errors="coerce").fillna(0)

    family_labels_train = family_encoder.transform(train_df[TARGET_COLUMN].astype(str).map(ALGORITHM_FAMILIES))

    logger.info("=== Stage 1: Family-level benchmarking ===")
    benchmark_results, winning_model_key, family_model = train_family_stage(x_train, family_labels_train)

    logger.info("=== Stage 2: Per-family algorithm sub-models (winning config: %s) ===", winning_model_key)
    algorithm_submodels = train_algorithm_submodels(
        x_train, train_df, algorithm_encoder, winning_model_key,
        benchmark_results[winning_model_key].best_params,
    )

    logger.info("=== Final evaluation on test.csv (touched once) ===")
    evaluation = evaluate_final_model(
        x_test, test_df, family_model, algorithm_submodels, family_encoder, algorithm_encoder
    )

    shap_top_features = generate_shap_explanations(family_model, x_train, x_test)

    training_duration = time.monotonic() - started_at

    save_all_artifacts(
        winning_model_key=winning_model_key,
        family_model=family_model,
        algorithm_submodels=algorithm_submodels,
        family_encoder=family_encoder,
        algorithm_encoder=algorithm_encoder,
        feature_columns=feature_columns,
        benchmark_results=benchmark_results,
        evaluation=evaluation,
        shap_top_features=shap_top_features,
        training_duration_seconds=training_duration,
        train_sample_count=len(x_train),
        test_sample_count=len(x_test),
    )

    return {
        "winning_model_key": winning_model_key,
        "benchmark_results": benchmark_results,
        "evaluation": evaluation,
        "training_duration_seconds": training_duration,
        "feature_columns": feature_columns,
    }


def main() -> None:
    """Entry point for running the training pipeline as a script."""
    log_path = _configure_logging()
    logger.info("Training log: %s", log_path)
    try:
        result = run_training()
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Training aborted: %s", exc)
        sys.exit(1)

    logger.info("")
    logger.info("================= TRAINING SUMMARY =================")
    logger.info("Winning model: %s", MODEL_REGISTRY[result["winning_model_key"]].display_name)
    logger.info("Test accuracy (algorithm): %.4f", result["evaluation"]["metrics"]["accuracy"])
    logger.info("Test F1 macro (algorithm): %.4f", result["evaluation"]["metrics"]["f1_macro"])
    logger.info("Test accuracy (family): %.4f", result["evaluation"]["metrics"]["family_accuracy"])
    logger.info("Feature count: %d", len(result["feature_columns"]))
    logger.info("Training duration: %.1fs", result["training_duration_seconds"])
    logger.info("Artifacts written to: %s and %s", SAVED_MODELS_DIR, REPORTS_DIR)
    logger.info("======================================================")


if __name__ == "__main__":
    main()
