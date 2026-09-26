from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

import config

logger = logging.getLogger("cryptosage.dataset.preprocess")

# Columns that identify a row rather than describe it numerically/
# categorically -- never encoded or normalized.
IDENTIFIER_COLUMNS: list[str] = ["binary_name"]

# The prediction target -- preserved as-is (never encoded away, though a
# label-encoded copy is added alongside it for convenience).
LABEL_COLUMN: str = "algorithm_label"

# Columns treated as categorical (label-encoded).
CATEGORICAL_COLUMNS: list[str] = [
    "project", "architecture", "optimization_level", "compiler",
    "compiler_version", "build_type", "build_system", "binary_type",
    "crypto_library",
]

# Boolean/flag columns are treated as numeric 0/1 rather than categorical.
BOOLEAN_COLUMNS: list[str] = [
    "aes_constant", "sha_constant", "sha1_constant", "md5_constant",
    "rsa_symbol", "ecc_symbol", "aes_symbol", "sha_symbol",
    "des_symbol", "chacha_symbol",
]

TRAIN_SPLIT_RATIO: float = 0.8
RANDOM_SEED: int = 42

# Deterministic fallback code used, at transform time, for a categorical
# value that was never seen while fitting the encoder on the training
# split (e.g. a category that -- by chance of the stratified split --
# only ended up in the test set). One past the highest training-fitted
# code, so it never collides with a legitimate training category and is
# always the same value for a given fitted encoder.
UNSEEN_CATEGORY_LABEL: str = "__UNSEEN__"


def load_raw_dataset(csv_path: Optional[Path] = None) -> pd.DataFrame:
    """Load the raw dataset CSV produced by builder.py."""
    csv_path = csv_path or (config.RAW_DATA_DIR / "dataset.csv")
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Raw dataset not found at {csv_path}. Run builder.py first."
        )
    dataframe = pd.read_csv(csv_path)
    logger.info("Loaded raw dataset: %d rows, %d columns from %s", len(dataframe), len(dataframe.columns), csv_path)
    return dataframe


def remove_duplicates(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Drop exact duplicate rows (same binary fingerprint across all columns)."""
    before = len(dataframe)
    deduplicated = dataframe.drop_duplicates().reset_index(drop=True)
    removed = before - len(deduplicated)
    logger.info("Removed %d duplicate row(s) (%d -> %d).", removed, before, len(deduplicated))
    return deduplicated


# ---------------------------------------------------------------------------
# 80/20 stratified split -- now run on RAW data, before any preprocessing
# statistic (median, min/max, categorical encoding) is fit. This is what
# guarantees the test split can never influence a fitted parameter.
# ---------------------------------------------------------------------------

def train_test_split(
    dataframe: pd.DataFrame,
    label_column: str = LABEL_COLUMN,
    train_ratio: float = TRAIN_SPLIT_RATIO,
    seed: int = RANDOM_SEED,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split the dataset 80/20 into train/test sets.

    Uses a per-class (stratified) split when every label class has at
    least 2 members (so both splits can contain at least one example);
    otherwise falls back to a plain random shuffle-split so a small or
    single-class dataset still produces valid output.

    Methodology is unchanged from the original implementation (same
    80/20 ratio, same stratification strategy, same random_state=42);
    only *when* this function is called relative to preprocessing moved
    (see `run_preprocessing`), to eliminate train/test leakage.
    """
    rng = np.random.default_rng(seed)

    class_counts = dataframe[label_column].value_counts()
    can_stratify = bool((class_counts >= 2).all()) and len(class_counts) > 0

    if can_stratify:
        train_parts, test_parts = [], []
        for label_value, group in dataframe.groupby(label_column):
            shuffled = group.sample(frac=1.0, random_state=seed).reset_index(drop=True)
            split_index = max(1, int(len(shuffled) * train_ratio))
            train_parts.append(shuffled.iloc[:split_index])
            test_parts.append(shuffled.iloc[split_index:])
        train_df = pd.concat(train_parts).sample(frac=1.0, random_state=seed).reset_index(drop=True)
        test_df = pd.concat(test_parts).sample(frac=1.0, random_state=seed).reset_index(drop=True)
        logger.info("Performed stratified 80/20 split across %d classes.", len(class_counts))
    else:
        shuffled_indices = rng.permutation(len(dataframe))
        split_index = max(1, int(len(dataframe) * train_ratio))
        train_indices = shuffled_indices[:split_index]
        test_indices = shuffled_indices[split_index:]
        train_df = dataframe.iloc[train_indices].reset_index(drop=True)
        test_df = dataframe.iloc[test_indices].reset_index(drop=True)
        logger.info("Performed plain random 80/20 split (stratification not possible).")

    logger.info("Train set: %d rows | Test set: %d rows", len(train_df), len(test_df))
    return train_df, test_df


# ---------------------------------------------------------------------------
# Missing-value handling -- fit (medians) on TRAIN ONLY, then apply the
# same fitted values to both train and test.
# ---------------------------------------------------------------------------

def compute_missing_value_stats(train_df: pd.DataFrame) -> dict:
    """Fit numeric-imputation statistics using TRAINING DATA ONLY.

    Returns a dict of:
      - "numeric_medians": {column: median} computed from the training
        split for every numeric column (so a column that only has
        missing values in the *test* split can still be imputed using a
        real, training-derived value).
      - "indicator_columns": numeric columns that had at least one
        missing value in the training split -- these get a
        `<column>_was_missing` indicator column added at transform time
        (added identically to train and test, so the two splits keep
        the exact same schema).
    """
    numeric_medians: dict[str, float] = {}
    indicator_columns: list[str] = []

    numeric_columns = train_df.select_dtypes(include=[np.number]).columns.tolist()
    for column in numeric_columns:
        missing_count = int(train_df[column].isna().sum())
        median_value = train_df[column].median()

        if pd.isna(median_value):
            # Every training value in this column is missing (e.g.
            # `import_libraries`-derived counts for object-file-only
            # samples). There is no real value to impute from, so fill
            # with 0 rather than a fabricated median.
            numeric_medians[column] = 0.0
            logger.info(
                "Column '%s' had no non-missing TRAINING values; imputation value set to 0.",
                column,
            )
        else:
            numeric_medians[column] = float(median_value)

        if missing_count > 0:
            indicator_columns.append(column)
            logger.info(
                "Column '%s': %d missing value(s) in TRAINING split; "
                "median=%s will be used for both train and test.",
                column, missing_count, numeric_medians[column],
            )

    return {
        "numeric_medians": numeric_medians,
        "indicator_columns": sorted(indicator_columns),
    }


def apply_missing_values(dataframe: pd.DataFrame, stats: dict) -> pd.DataFrame:
    """Apply training-fitted imputation statistics to a dataframe (train OR test).

    Never recomputes a median from `dataframe` itself -- always uses the
    values captured in `stats` (produced by `compute_missing_value_stats`
    on the training split only).
    """
    dataframe = dataframe.copy()

    # Indicator columns are added identically to every split so train
    # and test keep the same schema, even if this particular split has
    # zero missing values in that column.
    for column in stats["indicator_columns"]:
        if column in dataframe.columns:
            dataframe[f"{column}_was_missing"] = dataframe[column].isna().astype(int)

    for column, median_value in stats["numeric_medians"].items():
        if column not in dataframe.columns:
            continue
        remaining_missing = int(dataframe[column].isna().sum())
        if remaining_missing and column not in stats["indicator_columns"]:
            logger.warning(
                "Column '%s' has %d missing value(s) in this split despite having "
                "no missing values in the training split; imputing with the "
                "training-derived value %s (no indicator column added, to keep "
                "train/test schema identical to what feature selection saw).",
                column, remaining_missing, median_value,
            )
        dataframe[column] = dataframe[column].fillna(median_value)

    categorical_columns = dataframe.select_dtypes(include=["object"]).columns.tolist()
    for column in categorical_columns:
        if column == LABEL_COLUMN:
            continue  # never fabricate a label
        missing_count = int(dataframe[column].isna().sum())
        if missing_count == 0:
            continue
        dataframe[column] = dataframe[column].fillna("UNKNOWN")
        logger.info("Filled %d missing value(s) in categorical column '%s' with 'UNKNOWN'", missing_count, column)

    return dataframe


# ---------------------------------------------------------------------------
# Categorical encoding -- fit mapping on TRAIN ONLY, then apply the same
# mapping to both train and test. Unseen test-only categories are mapped
# to a single, deterministic fallback code rather than growing the
# training-fitted vocabulary or raising.
# ---------------------------------------------------------------------------

def fit_categorical_encoders(train_df: pd.DataFrame) -> dict[str, dict[str, int]]:
    """Fit label-encoding maps for `CATEGORICAL_COLUMNS` using TRAINING DATA ONLY."""
    encodings: dict[str, dict[str, int]] = {}
    for column in CATEGORICAL_COLUMNS:
        if column not in train_df.columns:
            continue
        unique_values = sorted(train_df[column].astype(str).unique())
        mapping = {value: index for index, value in enumerate(unique_values)}
        encodings[column] = mapping
        logger.info("Fitted categorical encoder for '%s' on TRAINING data (%d unique values).", column, len(mapping))
    return encodings


def apply_categorical_encoders(
    dataframe: pd.DataFrame, encodings: dict[str, dict[str, int]]
) -> pd.DataFrame:
    """Transform a dataframe (train OR test) using training-fitted encoders.

    A category value present in `dataframe` but absent from the fitted
    mapping (only possible for the test split) is handled safely and
    deterministically: it is assigned the fixed fallback code
    `len(mapping)` -- one past every legitimate training-fitted code --
    rather than silently colliding with a real category or crashing.
    """
    dataframe = dataframe.copy()

    for column, mapping in encodings.items():
        if column not in dataframe.columns:
            continue
        string_values = dataframe[column].astype(str)
        unseen_mask = ~string_values.isin(mapping.keys())
        unseen_count = int(unseen_mask.sum())

        encoded = string_values.map(mapping)
        if unseen_count:
            fallback_code = len(mapping)
            encoded = encoded.where(~unseen_mask, fallback_code)
            logger.warning(
                "Column '%s': %d value(s) in this split were never seen while "
                "fitting the encoder on the training split; mapped to the fixed "
                "fallback code %d instead of a training-fitted code.",
                column, unseen_count, fallback_code,
            )
        dataframe[f"{column}_encoded"] = encoded.astype(int)

    # Boolean feature columns become clean 0/1 integers. This is a fixed,
    # stateless transform (True/False -> 1/0) -- it needs no statistics
    # fit on training data, so it is safe to apply identically to both
    # splits independently.
    for column in BOOLEAN_COLUMNS:
        if column not in dataframe.columns:
            continue
        dataframe[column] = dataframe[column].map(
            {True: 1, False: 0, "True": 1, "False": 0, 1: 1, 0: 0}
        ).fillna(0).astype(int)

    return dataframe


# ---------------------------------------------------------------------------
# Min-Max normalization -- fit min/max on TRAIN ONLY, then apply the same
# fitted parameters to both train and test. Test values that fall outside
# the training min/max range are intentionally left outside [0, 1] (this
# is the correct behavior for a scaler fit on training data only, not a
# bug); they are never used to recompute the range.
# ---------------------------------------------------------------------------

def fit_numeric_scaler(train_df: pd.DataFrame) -> dict[str, dict[str, float]]:
    """Fit Min-Max scaler parameters using TRAINING DATA ONLY."""
    scaler_params: dict[str, dict[str, float]] = {}

    exclude = set(IDENTIFIER_COLUMNS) | {LABEL_COLUMN}
    exclude |= {f"{c}_encoded" for c in CATEGORICAL_COLUMNS}
    exclude |= set(BOOLEAN_COLUMNS)
    exclude |= {c for c in train_df.columns if c.endswith("_was_missing")}

    numeric_columns = [
        column
        for column in train_df.select_dtypes(include=[np.number]).columns
        if column not in exclude and not column.endswith("_was_missing")
    ]

    for column in numeric_columns:
        min_value = float(train_df[column].min())
        max_value = float(train_df[column].max())
        scaler_params[column] = {"min": min_value, "max": max_value}

    logger.info("Fitted Min-Max scaler on TRAINING data for %d numeric column(s).", len(scaler_params))
    return scaler_params


def apply_numeric_scaler(
    dataframe: pd.DataFrame, scaler_params: dict[str, dict[str, float]]
) -> pd.DataFrame:
    """Transform a dataframe (train OR test) using training-fitted Min-Max parameters."""
    dataframe = dataframe.copy()

    for column, params in scaler_params.items():
        if column not in dataframe.columns:
            continue
        min_value = params["min"]
        max_value = params["max"]
        value_range = max_value - min_value

        if value_range == 0:
            dataframe[f"{column}_normalized"] = 0.0
        else:
            dataframe[f"{column}_normalized"] = (dataframe[column] - min_value) / value_range

    return dataframe


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run_preprocessing(raw_csv_path: Optional[Path] = None) -> tuple[Path, Path]:
    """Run the full preprocessing pipeline and write train.csv / test.csv.

    Pipeline (leakage-safe):

        raw data
          -> exact duplicate removal
          -> 80/20 stratified train/test split
          -> fit missing-value medians on TRAIN ONLY -> apply to train & test
          -> fit categorical encoders on TRAIN ONLY -> apply to train & test
          -> fit Min-Max scaler on TRAIN ONLY -> apply to train & test
          -> write train.csv / test.csv

    No statistic used to transform the test split is ever computed from
    the test split itself.

    Returns the (train_csv_path, test_csv_path) written.
    """
    dataframe = load_raw_dataset(raw_csv_path)

    train_path = config.PROCESSED_DATA_DIR / "train.csv"
    test_path = config.PROCESSED_DATA_DIR / "test.csv"

    if dataframe.empty:
        logger.warning("Raw dataset is empty; writing empty train.csv/test.csv.")
        dataframe.to_csv(train_path, index=False)
        dataframe.to_csv(test_path, index=False)
        return train_path, test_path

    dataframe = remove_duplicates(dataframe)

    # Split FIRST, on raw (deduplicated) data -- before any preprocessing
    # statistic is computed, so nothing about the test split can leak
    # into a fitted parameter.
    train_df, test_df = train_test_split(dataframe)

    # --- Missing values: fit on train, apply to both -----------------------
    missing_value_stats = compute_missing_value_stats(train_df)
    train_df = apply_missing_values(train_df, missing_value_stats)
    test_df = apply_missing_values(test_df, missing_value_stats)

    # --- Categorical encoding: fit on train, apply to both ------------------
    categorical_encodings = fit_categorical_encoders(train_df)
    train_df = apply_categorical_encoders(train_df, categorical_encodings)
    test_df = apply_categorical_encoders(test_df, categorical_encodings)

    # --- Min-Max normalization: fit on train, apply to both -----------------
    numeric_scaler_params = fit_numeric_scaler(train_df)
    train_df = apply_numeric_scaler(train_df, numeric_scaler_params)
    test_df = apply_numeric_scaler(test_df, numeric_scaler_params)

    # Sanity check (see "Required Testing" #12): train/test feature
    # columns must match exactly after independent transforms.
    if list(train_df.columns) != list(test_df.columns):
        train_only = set(train_df.columns) - set(test_df.columns)
        test_only = set(test_df.columns) - set(train_df.columns)
        logger.error(
            "Train/test column mismatch after preprocessing! train_only=%s test_only=%s",
            sorted(train_only), sorted(test_only),
        )
        raise ValueError("Train and test feature columns do not match after preprocessing.")

    preprocessing_metadata = {
        "categorical_encodings": categorical_encodings,
        "numeric_medians": missing_value_stats["numeric_medians"],
        "missing_value_indicator_columns": missing_value_stats["indicator_columns"],
        "numeric_scaler_params": numeric_scaler_params,
        "train_split_ratio": TRAIN_SPLIT_RATIO,
        "random_seed": RANDOM_SEED,
        "fit_on": "training_split_only",
    }
    metadata_path = config.PROCESSED_DATA_DIR / "preprocessing_metadata.json"
    metadata_path.write_text(json.dumps(preprocessing_metadata, indent=2, default=str), encoding="utf-8")
    logger.info("Wrote preprocessing metadata to %s", metadata_path)

    train_df.to_csv(train_path, index=False)
    test_df.to_csv(test_path, index=False)
    logger.info("Wrote train set to %s (%d rows)", train_path, len(train_df))
    logger.info("Wrote test set to %s (%d rows)", test_path, len(test_df))

    return train_path, test_path


def main() -> None:
    """Entry point for running preprocessing as a standalone script."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    run_preprocessing()


if __name__ == "__main__":
    main()