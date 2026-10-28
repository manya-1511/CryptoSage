
"""
analysis/pipeline.py

Firmware Analysis Engine pipeline orchestrator (Phase 4).

Workflow:
  1. Resolve the uploaded firmware source.
  2. Acquire a per-firmware execution lock.
  3. Extract into a unique directory for this run.
  4. Discover binaries from fresh extraction output, or from the
     original-firmware copy if Binwalk fails.
  5. Extract features independently for each discovered binary.
  6. Publish successful run artifacts and replace feature rows atomically.
  7. Persist the final lifecycle status.

A successful Binwalk execution alone does not constitute a successful
analysis. At least one binary must have its features extracted and saved.
"""

from __future__ import annotations

import logging
import os
import shutil
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from fastapi import HTTPException, status
from sqlalchemy import text
from database import engine
from sqlalchemy.orm import Session

from analysis.binary import discover_binaries
from analysis.features import extract_features, save_feature_vector
from analysis.firmware import extract_firmware
from config import get_settings
from models import Firmware, FirmwareStatus, UploadedFeatures
from schemas import FirmwareAnalysisResponse, FirmwareAnalysisResult

logger = logging.getLogger("cryptosage.analysis.pipeline")
settings = get_settings()

# PostgreSQL session-level advisory lock namespace. Keep this constant
# stable across application workers.
_ADVISORY_LOCK_NAMESPACE = 731204
_local_locks_guard = threading.Lock()
_local_firmware_locks: dict[int, threading.Lock] = {}


def _get_local_lock(firmware_id: int) -> threading.Lock:
    """Get a process-local fallback lock for non-PostgreSQL databases."""
    with _local_locks_guard:
        lock = _local_firmware_locks.get(firmware_id)
        if lock is None:
            lock = threading.Lock()
            _local_firmware_locks[firmware_id] = lock
        return lock



@contextmanager
def _firmware_run_lock(
    db: Session,
    firmware_id: int,
) -> Iterator[None]:
    """
    Prevent overlapping analysis runs for the same firmware.

    PostgreSQL uses a dedicated connection held for the entire run.
    The connection is not managed by the ORM Session, so ORM commits
    cannot return the lock-holding connection to the pool prematurely.

    Other database dialects use a process-local fallback only.
    """
    dialect_name = db.get_bind().dialect.name

    if dialect_name == "postgresql":
        lock_connection = engine.connect()

        try:
            acquired = lock_connection.execute(
                text(
                    "SELECT pg_try_advisory_lock("
                    ":namespace, :firmware_id)"
                ),
                {
                    "namespace": _ADVISORY_LOCK_NAMESPACE,
                    "firmware_id": firmware_id,
                },
            ).scalar_one()

            # End the SQL transaction, but retain the connection.
            # PostgreSQL session-level advisory locks survive commits.
            lock_connection.commit()

            if not acquired:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Analysis is already running for this firmware.",
                )

            try:
                yield
            finally:
                try:
                    released = lock_connection.execute(
                        text(
                            "SELECT pg_advisory_unlock("
                            ":namespace, :firmware_id)"
                        ),
                        {
                            "namespace": _ADVISORY_LOCK_NAMESPACE,
                            "firmware_id": firmware_id,
                        },
                    ).scalar_one()

                    lock_connection.commit()

                    if not released:
                        logger.error(
                            "PostgreSQL advisory lock was not held when "
                            "releasing firmware_id=%d",
                            firmware_id,
                        )

                except Exception:
                    lock_connection.rollback()
                    logger.exception(
                        "Failed to release advisory lock for firmware_id=%d",
                        firmware_id,
                    )
                    raise

        finally:
            lock_connection.close()

    else:
        lock = _get_local_lock(firmware_id)

        if not lock.acquire(blocking=False):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Analysis is already running for this firmware.",
            )

        try:
            yield
        finally:
            lock.release()


def _resolve_firmware_path(storage_path: str) -> Path:
    """Resolve a stored firmware path without exposing it in API errors."""
    path = Path(storage_path)

    if not path.is_absolute():
        path = Path(settings.UPLOAD_DIR) / path

    return path.resolve()


def _archive_existing_output(
    final_dir: Path,
    archive_dir: Path,
) -> bool:
    """
    Move existing published artifacts out of the canonical output path.

    Returns True when an existing directory was moved. The caller can
    restore it if publishing or the database transaction fails.
    """
    if not final_dir.exists():
        return False

    archive_dir.parent.mkdir(parents=True, exist_ok=True)

    if archive_dir.exists():
        shutil.rmtree(archive_dir)

    os.replace(final_dir, archive_dir)
    return True


def _restore_archived_output(
    final_dir: Path,
    archive_dir: Path,
    had_previous_output: bool,
) -> None:
    """Restore previously published artifacts after a failed publication."""
    if final_dir.exists():
        shutil.rmtree(final_dir)

    if had_previous_output and archive_dir.exists():
        final_dir.parent.mkdir(parents=True, exist_ok=True)
        os.replace(archive_dir, final_dir)


def _remove_directory(path: Path) -> None:
    """Remove a run directory without masking the primary error."""
    try:
        if path.exists():
            shutil.rmtree(path)
    except OSError:
        logger.warning(
            "Could not remove temporary analysis directory: %s",
            path,
            exc_info=True,
        )


def run_firmware_analysis(
    firmware_id: int,
    db: Session,
) -> FirmwareAnalysisResponse:
    """
    Run firmware extraction, binary discovery, and feature extraction.

    A run is considered successful only when at least one binary has
    been analyzed and its feature vector has been saved successfully.
    """
    start_time = time.perf_counter()

    output_root = Path(settings.ANALYSIS_OUTPUT_DIR).resolve()
    run_id = uuid.uuid4().hex

    # A unique output root prevents a retry from reusing files left by
    # an earlier attempt for the same firmware.
    run_root = output_root / ".runs" / str(firmware_id) / run_id
    staged_output_dir = run_root / str(firmware_id)

    final_output_dir = output_root / str(firmware_id)
    archive_dir = (
        output_root
        / ".archive"
        / str(firmware_id)
        / run_id
        / "previous_output"
    )

    with _firmware_run_lock(db, firmware_id):
        firmware = (
            db.query(Firmware)
            .filter(Firmware.id == firmware_id)
            .with_for_update()
            .first()
        )

        if firmware is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Firmware with id {firmware_id} was not found.",
            )

        if not firmware.storage_path:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No storage path is recorded for this firmware.",
            )

        try:
            file_path = _resolve_firmware_path(firmware.storage_path)
        except (OSError, RuntimeError, ValueError) as exc:
            logger.warning(
                "Could not resolve source path for firmware_id=%d: %s",
                firmware_id,
                exc,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The stored firmware path is invalid.",
            ) from exc

        if not file_path.is_file():
            logger.error(
                "Firmware source is missing for firmware_id=%d",
                firmware_id,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The uploaded firmware file could not be found.",
            )

        # Persist the initial transition. A database failure must stop
        # the run; continuing would make the lifecycle unreliable.
        firmware.status = FirmwareStatus.EXTRACTING

        try:
            db.add(firmware)
            db.commit()
            db.refresh(firmware)
        except Exception as exc:
            db.rollback()
            logger.exception(
                "Could not set EXTRACTING status for firmware_id=%d",
                firmware_id,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not start firmware analysis.",
            ) from exc

        try:
            output_root.mkdir(parents=True, exist_ok=True)
            run_root.mkdir(parents=True, exist_ok=False)

            extraction_result = extract_firmware(
                firmware_path=file_path,
                firmware_id=firmware_id,
                output_root=run_root,
            )

            if extraction_result.output_dir is None:
                # No isolated directory means there is no safe directory
                # to inspect. Do not fall back to the canonical output.
                discovered_binaries = []
                extraction_message = extraction_result.message
            else:
                output_dir = extraction_result.output_dir

                # When Binwalk fails, inspect only the fresh copy of the
                # original upload. Do not analyze potentially incomplete
                # extraction artifacts from the failed attempt.
                discovery_root = (
                    output_dir
                    if extraction_result.success
                    else output_dir / "original"
                )

                firmware.status = FirmwareStatus.ANALYZING

                try:
                    db.add(firmware)
                    db.commit()
                    db.refresh(firmware)
                except Exception as exc:
                    db.rollback()
                    logger.exception(
                        "Could not set ANALYZING status for firmware_id=%d",
                        firmware_id,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Could not update the analysis lifecycle status.",
                    ) from exc

                discovered_binaries = discover_binaries(discovery_root)
                extraction_message = extraction_result.message

            logger.info(
                "Discovered %d binaries for firmware_id=%d",
                len(discovered_binaries),
                firmware_id,
            )

            analyzed_results: list[FirmwareAnalysisResult] = []
            new_feature_rows: list[UploadedFeatures] = []
            primary_architecture: Optional[str] = None

            for binary_path in discovered_binaries:
                try:
                    features = extract_features(binary_path)
                    features["binary_name"] = binary_path.name

                    architecture = features.get("architecture")
                    if architecture and not primary_architecture:
                        primary_architecture = architecture

                    vector_path = (
                        binary_path.parent
                        / f"{binary_path.stem}_feature_vector.json"
                    )

                    save_feature_vector(features, vector_path)

                    # Stage the ORM objects in memory. Old feature records
                    # are not deleted until at least one binary succeeds.
                    new_feature_rows.append(
                        UploadedFeatures(
                            firmware_id=firmware_id,
                            feature_vector=features,
                        )
                    )

                    feature_count = sum(
                        1
                        for value in features.values()
                        if value is not None
                    )

                    analyzed_results.append(
                        FirmwareAnalysisResult(
                            binary_name=binary_path.name,
                            architecture=architecture,
                            binary_size=features.get("binary_size"),
                            feature_count=feature_count,
                            feature_vector_path=str(vector_path),
                        )
                    )

                except Exception:
                    logger.exception(
                        "Failed to analyze binary %s for firmware_id=%d",
                        binary_path,
                        firmware_id,
                    )

            # A successful Binwalk run with zero analyzable binaries is
            # not a completed firmware analysis.
            if not analyzed_results:
                firmware.status = FirmwareStatus.FAILED

                try:
                    db.add(firmware)
                    db.commit()
                    db.refresh(firmware)
                except Exception as exc:
                    db.rollback()
                    logger.exception(
                        "Could not persist FAILED status for firmware_id=%d",
                        firmware_id,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Analysis failed and its final status could not be saved.",
                    ) from exc

                return FirmwareAnalysisResponse(
                    firmware_id=firmware_id,
                    status=firmware.status,
                    extraction_success=extraction_result.success,
                    extraction_message=extraction_message,
                    binaries_discovered=len(discovered_binaries),
                    analyzed_binaries=[],
                    analysis_time_ms=round(
                        (time.perf_counter() - start_time) * 1000,
                        2,
                    ),
                )

            # All feature files and records were produced in the isolated
            # run directory. Publish only after at least one binary has
            # been analyzed successfully.
            had_previous_output = _archive_existing_output(
                final_output_dir,
                archive_dir,
            )

            try:
                final_output_dir.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staged_output_dir, final_output_dir)

                # Return canonical paths rather than temporary run paths.
                for result in analyzed_results:
                    old_path = Path(result.feature_vector_path)
                    relative_path = old_path.relative_to(staged_output_dir)
                    result.feature_vector_path = str(
                        final_output_dir / relative_path
                    )

                # Replace the previous feature records within the same
                # database transaction as the new records and final status.
                db.query(UploadedFeatures).filter(
                    UploadedFeatures.firmware_id == firmware_id
                ).delete(synchronize_session=False)

                db.add_all(new_feature_rows)

                if primary_architecture and not firmware.architecture:
                    firmware.architecture = primary_architecture

                firmware.status = FirmwareStatus.COMPLETED
                db.add(firmware)
                db.commit()
                db.refresh(firmware)

            except Exception as exc:
                db.rollback()

                # Restore the previous published artifacts if the DB
                # transaction or filesystem publication failed.
                try:
                    _restore_archived_output(
                        final_output_dir,
                        archive_dir,
                        had_previous_output,
                    )
                except Exception:
                    logger.exception(
                        "Could not restore prior artifacts for firmware_id=%d",
                        firmware_id,
                    )

                logger.exception(
                    "Could not finalize analysis for firmware_id=%d",
                    firmware_id,
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Could not finalize firmware analysis.",
                ) from exc

            # The new DB records and published artifacts are now committed.
            # Old artifacts are no longer needed.
            _remove_directory(archive_dir)

            return FirmwareAnalysisResponse(
                firmware_id=firmware_id,
                status=firmware.status,
                extraction_success=extraction_result.success,
                extraction_message=extraction_message,
                binaries_discovered=len(discovered_binaries),
                analyzed_binaries=analyzed_results,
                analysis_time_ms=round(
                    (time.perf_counter() - start_time) * 1000,
                    2,
                ),
            )

        except HTTPException:
            raise

        except Exception as exc:
            db.rollback()

            logger.exception(
                "Unexpected analysis failure for firmware_id=%d",
                firmware_id,
            )

            # Best-effort persistence of FAILED status. Do not claim
            # success if this commit also fails.
            try:
                failed_firmware = (
                    db.query(Firmware)
                    .filter(Firmware.id == firmware_id)
                    .first()
                )
                if failed_firmware is not None:
                    failed_firmware.status = FirmwareStatus.FAILED
                    db.add(failed_firmware)
                    db.commit()
            except Exception:
                db.rollback()
                logger.exception(
                    "Could not persist FAILED status for firmware_id=%d",
                    firmware_id,
                )

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Firmware analysis failed.",
            ) from exc

        finally:
            # Only remove this run's temporary directory. Never remove
            # or modify the uploaded source firmware.
            _remove_directory(run_root)
