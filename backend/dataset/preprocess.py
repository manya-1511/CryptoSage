"""
dataset/preprocess.py

Phase 2A -- preprocessing step for the offline dataset builder.

Takes the raw `dataset.csv` produced by `builder.py` and prepares it for
future ML training:

    1. Remove duplicate rows.
    2. Handle missing values (numeric -> median imputation with a
       `<column>_was_missing` indicator; categorical -> "UNKNOWN").
    3. Encode categorical columns using deterministic label encoding
       (mappings are saved alongside the output so they can be reversed
       or reused at inference time).
    4. Normalize numeric feature columns with min-max scaling (scaler
       parameters are saved alongside the output for the same reason).
    5. Split into train/test sets (80/20, stratified by `algorithm_label`
       when every class has enough members, otherwise a plain random
       split) and write `train.csv` / `test.csv`.

No model is trained here -- this module only prepares data. Scikit-learn
is intentionally not used (per Phase 2A constraints); the encoding,
normalization, and splitting are implemented directly with pandas/numpy.
"""

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


def handle_missing_values(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Impute missing values without discarding rows.

    Numeric columns: median imputation, plus a `<column>_was_missing`
    binary indicator so the fact that a value was imputed is preserved
    as information rather than silently hidden.
    Categorical columns: filled with the literal string "UNKNOWN".
    """
    dataframe = dataframe.copy()

    numeric_columns = dataframe.select_dtypes(include=[np.number]).columns.tolist()
    for column in numeric_columns:
        missing_count = dataframe[column].isna().sum()
        if missing_count == 0:
            continue
        indicator_column = f"{column}_was_missing"
        dataframe[indicator_column] = dataframe[column].isna().astype(int)
        median_value = dataframe[column].median()
        if pd.isna(median_value):
            # Every value in this column is missing (e.g. `import_libraries`
            # is naturally always empty for standalone object-file
            # samples, which have no dynamic dependencies). There is no
            # real value to impute from, so fill with 0 rather than a
            # fabricated median, and rely on the `_was_missing` indicator
            # to preserve the fact that this feature was unavailable.
            dataframe[column] = dataframe[column].fillna(0)
            logger.info(
                "Column '%s' had no non-missing values; filled with 0 (see '%s').",
                column, indicator_column,
            )
            continue
        dataframe[column] = dataframe[column].fillna(median_value)
        logger.info(
            "Imputed %d missing value(s) in numeric column '%s' with median=%s",
            missing_count, column, median_value,
        )

    categorical_columns = dataframe.select_dtypes(include=["object"]).columns.tolist()
    for column in categorical_columns:
        if column == LABEL_COLUMN:
            continue  # never fabricate a label
        missing_count = dataframe[column].isna().sum()
        if missing_count == 0:
            continue
        dataframe[column] = dataframe[column].fillna("UNKNOWN")
        logger.info("Filled %d missing value(s) in categorical column '%s' with 'UNKNOWN'", missing_count, column)

    return dataframe


def encode_categorical_columns(
    dataframe: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, dict[str, int]]]:
    """Label-encode configured categorical columns.

    Returns the modified dataframe (original column kept, `<column>_encoded`
    added) plus the encoding map used, so it can be persisted and reused.
    """
    dataframe = dataframe.copy()
    encodings: dict[str, dict[str, int]] = {}

    for column in CATEGORICAL_COLUMNS:
        if column not in dataframe.columns:
            continue
        unique_values = sorted(dataframe[column].astype(str).unique())
        mapping = {value: index for index, value in enumerate(unique_values)}
        dataframe[f"{column}_encoded"] = dataframe[column].astype(str).map(mapping)
        encodings[column] = mapping
        logger.info("Encoded categorical column '%s' (%d unique values)", column, len(mapping))

    # Boolean feature columns become clean 0/1 integers.
    for column in BOOLEAN_COLUMNS:
        if column not in dataframe.columns:
            continue
        dataframe[column] = dataframe[column].map(
            {True: 1, False: 0, "True": 1, "False": 0, 1: 1, 0: 0}
        ).fillna(0).astype(int)

    return dataframe, encodings


def normalize_numeric_columns(
    dataframe: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, dict[str, float]]]:
    """Apply min-max normalization to continuous numeric feature columns.

    Identifier columns, encoded categorical columns, boolean flag
    columns, and the label are excluded from normalization.
    """
    dataframe = dataframe.copy()
    scaler_params: dict[str, dict[str, float]] = {}

    exclude = set(IDENTIFIER_COLUMNS) | {LABEL_COLUMN}
    exclude |= {f"{c}_encoded" for c in CATEGORICAL_COLUMNS}
    exclude |= set(BOOLEAN_COLUMNS)
    exclude |= {f"{c}_was_missing" for c in dataframe.columns if c.endswith("_was_missing")}

    numeric_columns = [
        column
        for column in dataframe.select_dtypes(include=[np.number]).columns
        if column not in exclude and not column.endswith("_was_missing")
    ]

    for column in numeric_columns:
        min_value = float(dataframe[column].min())
        max_value = float(dataframe[column].max())
        value_range = max_value - min_value

        if value_range == 0:
            dataframe[f"{column}_normalized"] = 0.0
        else:
            dataframe[f"{column}_normalized"] = (dataframe[column] - min_value) / value_range

        scaler_params[column] = {"min": min_value, "max": max_value}

    logger.info("Normalized %d numeric column(s).", len(numeric_columns))
    return dataframe, scaler_params


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


def run_preprocessing(raw_csv_path: Optional[Path] = None) -> tuple[Path, Path]:
    """Run the full preprocessing pipeline and write train.csv / test.csv.

    Returns the (train_csv_path, test_csv_path) written.
    """
    dataframe = load_raw_dataset(raw_csv_path)

    if dataframe.empty:
        logger.warning("Raw dataset is empty; writing empty train.csv/test.csv.")
        train_path = config.PROCESSED_DATA_DIR / "train.csv"
        test_path = config.PROCESSED_DATA_DIR / "test.csv"
        dataframe.to_csv(train_path, index=False)
        dataframe.to_csv(test_path, index=False)
        return train_path, test_path

    dataframe = remove_duplicates(dataframe)
    dataframe = handle_missing_values(dataframe)
    dataframe, encodings = encode_categorical_columns(dataframe)
    dataframe, scaler_params = normalize_numeric_columns(dataframe)

    preprocessing_metadata = {
        "categorical_encodings": encodings,
        "numeric_scaler_params": scaler_params,
        "train_split_ratio": TRAIN_SPLIT_RATIO,
        "random_seed": RANDOM_SEED,
    }
    metadata_path = config.PROCESSED_DATA_DIR / "preprocessing_metadata.json"
    metadata_path.write_text(json.dumps(preprocessing_metadata, indent=2, default=str), encoding="utf-8")
    logger.info("Wrote preprocessing metadata to %s", metadata_path)

    train_df, test_df = train_test_split(dataframe)

    train_path = config.PROCESSED_DATA_DIR / "train.csv"
    test_path = config.PROCESSED_DATA_DIR / "test.csv"
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
