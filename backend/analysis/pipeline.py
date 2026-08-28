"""
analysis/pipeline.py

Firmware Analysis Engine pipeline orchestrator (Phase 4).

Executes the automated analysis workflow for an uploaded firmware image:
  1. Resolves stored firmware file path on disk.
  2. Extracts embedded file system and binaries using Binwalk via `analysis.firmware`.
  3. Discovers ELF binaries via static inspection (`analysis.binary`).
  4. Extracts static feature vectors for each binary (`analysis.features`).
  5. Saves `*_feature_vector.json` files in `ANALYSIS_OUTPUT_DIR/<firmware_id>/`
     so down-stream endpoints (`/predict`, `/risk`, `/explain`) can consume them.
  6. Stores `UploadedFeatures` records in the database.
  7. Updates `Firmware` lifecycle status (EXTRACTING -> ANALYZING -> COMPLETED/FAILED).
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from analysis.binary import discover_binaries
from analysis.features import extract_features, save_feature_vector
from analysis.firmware import extract_firmware
from config import get_settings
from models import Firmware, FirmwareStatus, UploadedFeatures
from schemas import FirmwareAnalysisResponse, FirmwareAnalysisResult

logger = logging.getLogger("cryptosage.analysis.pipeline")
settings = get_settings()


def run_firmware_analysis(firmware_id: int, db: Session) -> FirmwareAnalysisResponse:
    """Run full Phase 4 firmware extraction, binary discovery, and feature extraction.

    Args:
        firmware_id: ID of the uploaded firmware record in the database.
        db: Active SQLAlchemy database session.

    Returns:
        FirmwareAnalysisResponse summarizing extraction and feature extraction results.
    """
    start_time = time.perf_counter()

    firmware = db.query(Firmware).filter(Firmware.id == firmware_id).first()
    if firmware is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Firmware with id {firmware_id} was not found.",
        )

    if not firmware.storage_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Firmware with id {firmware_id} has no storage path recorded.",
        )

    file_path = Path(firmware.storage_path)
    if not file_path.is_absolute():
        file_path = settings.UPLOAD_DIR / file_path

    if not file_path.exists():
        logger.error("Firmware file missing on disk at %s for firmware_id=%d", file_path, firmware_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Firmware file was not found on disk at {file_path}.",
        )

    # 1. Update status to EXTRACTING
    firmware.status = FirmwareStatus.EXTRACTING
    try:
        db.add(firmware)
        db.commit()
        db.refresh(firmware)
    except Exception as exc:
        db.rollback()
        logger.error("Failed to update firmware status to EXTRACTING: %s", exc)

    # 2. Extract firmware using Binwalk
    output_root = settings.ANALYSIS_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    extraction_result = extract_firmware(
        firmware_path=file_path,
        firmware_id=firmware_id,
        output_root=output_root,
    )

    # 3. Update status to ANALYZING
    firmware.status = FirmwareStatus.ANALYZING
    try:
        db.add(firmware)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Failed to update firmware status to ANALYZING: %s", exc)

    output_dir = extraction_result.output_dir or (output_root / str(firmware_id))
    output_dir.mkdir(parents=True, exist_ok=True)

    # 4. Discover binaries inside output_dir
    discovered_binaries = discover_binaries(output_dir)
    logger.info("Discovered %d binaries for firmware_id=%d in %s", len(discovered_binaries), firmware_id, output_dir)

    analyzed_results: list[FirmwareAnalysisResult] = []
    primary_architecture: Optional[str] = None

    # 5. Extract features for each binary
    for binary_path in discovered_binaries:
        try:
            features = extract_features(binary_path)
            binary_name = binary_path.name
            features["binary_name"] = binary_name

            arch = features.get("architecture")
            if arch and not primary_architecture:
                primary_architecture = arch

            # Save feature vector to disk under firmware analysis output dir
            vector_filename = f"{binary_path.stem}_feature_vector.json"
            feature_vector_path = binary_path.parent / vector_filename

            save_feature_vector(features, feature_vector_path)

            # Store UploadedFeatures record in DB
            uploaded_feature_row = UploadedFeatures(
                firmware_id=firmware_id,
                feature_vector=features,
            )
            db.add(uploaded_feature_row)

            feature_count = sum(1 for v in features.values() if v is not None)

            analyzed_results.append(
                FirmwareAnalysisResult(
                    binary_name=binary_name,
                    architecture=arch,
                    binary_size=features.get("binary_size"),
                    feature_count=feature_count,
                    feature_vector_path=str(feature_vector_path),
                )
            )
        except Exception as exc:
            logger.exception("Error analyzing binary %s for firmware_id=%d: %s", binary_path, firmware_id, exc)

    # 6. Finalize status and DB record
    if analyzed_results or extraction_result.success:
        firmware.status = FirmwareStatus.COMPLETED
    else:
        firmware.status = FirmwareStatus.FAILED

    if primary_architecture and not firmware.architecture:
        firmware.architecture = primary_architecture

    try:
        db.add(firmware)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Failed to update final status for firmware_id=%d: %s", firmware_id, exc)

    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

    return FirmwareAnalysisResponse(
        firmware_id=firmware_id,
        status=firmware.status,
        extraction_success=extraction_result.success,
        extraction_message=extraction_result.message,
        binaries_discovered=len(discovered_binaries),
        analyzed_binaries=analyzed_results,
        analysis_time_ms=elapsed_ms,
    )
