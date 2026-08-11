"""
input/upload.py

Core firmware upload logic (Phase 3 -- Firmware Input Module).

Handles the full intake workflow for a single uploaded firmware file:

    1. Validate the upload's filename/extension/MIME type (via
       `input.validator`) before touching the disk.
    2. Stream the file to a temporary location while computing its
       SHA-256 hash, enforcing the empty-file and maximum-size checks
       as the stream is read (never loading the whole file into memory).
    3. Check the computed hash against existing `firmware` records; if
       a match is found, the temporary file is discarded and the
       existing record's ID is returned instead of creating a duplicate.
    4. Otherwise, insert a new `firmware` row (status = "Uploaded"),
       move the temporary file into its final, ID-scoped location under
       `uploads/<firmware_id>/<original_filename>`, and record the
       relative storage path on the row.

This module is only responsible for firmware intake -- it does not
extract, analyze, or otherwise inspect the firmware's contents.
"""

from __future__ import annotations

import hashlib
import logging
import shutil
import uuid
from pathlib import Path
from typing import BinaryIO

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from config import get_settings
from input.validator import (
    validate_max_size,
    validate_not_empty,
    validate_upload_metadata,
)
from models import Firmware, FirmwareStatus
from schemas import FirmwareDuplicateResponse, FirmwareUploadResponse

logger = logging.getLogger("cryptosage.input.upload")

settings = get_settings()

# Read/write files in 1 MiB chunks so arbitrarily large firmware images
# never need to be loaded into memory all at once.
_CHUNK_SIZE_BYTES = 1024 * 1024


def _temp_upload_path() -> Path:
    """Build a unique temporary path to stream an in-progress upload into."""
    temp_dir = settings.UPLOAD_DIR / ".tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir / f"{uuid.uuid4().hex}.part"


def _stream_to_temp_file_and_hash(source: BinaryIO) -> tuple[Path, str, int]:
    """Stream `source` to a temporary file, hashing and sizing it as it goes.

    The file is never read into memory in full: it is read and written
    in fixed-size chunks, with the SHA-256 hash updated incrementally
    (`hashlib.sha256()`). The maximum-size check is enforced *during*
    the stream so an oversized upload is rejected without needing to
    finish writing it to disk first.

    Raises:
        HTTPException(413): if the stream exceeds the configured
            maximum upload size.

    Returns:
        A tuple of (temp_file_path, sha256_hexdigest, total_bytes_read).
    """
    temp_path = _temp_upload_path()
    sha256 = hashlib.sha256()
    total_bytes = 0
    max_bytes = settings.max_upload_size_bytes

    try:
        with temp_path.open("wb") as destination:
            while True:
                chunk = source.read(_CHUNK_SIZE_BYTES)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    logger.warning(
                        "Upload aborted mid-stream: exceeded maximum size of %d bytes.",
                        max_bytes,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=(
                            f"Firmware file exceeds the maximum allowed size of "
                            f"{settings.MAX_UPLOAD_SIZE_MB} MB."
                        ),
                    )
                sha256.update(chunk)
                destination.write(chunk)
    except HTTPException:
        temp_path.unlink(missing_ok=True)
        raise
    except OSError as exc:
        temp_path.unlink(missing_ok=True)
        logger.error("Storage failure while streaming upload to disk: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store the uploaded firmware file.",
        ) from exc

    logger.info(
        "SHA-256 generation completed: %d bytes hashed to %s", total_bytes, sha256.hexdigest()
    )
    return temp_path, sha256.hexdigest(), total_bytes


def _find_existing_firmware_by_hash(db: Session, file_hash: str) -> Firmware | None:
    """Look up an existing firmware record with the same SHA-256 hash."""
    return db.query(Firmware).filter(Firmware.file_hash == file_hash).first()


def _create_firmware_record(db: Session, filename: str, file_hash: str, file_size: int) -> Firmware:
    """Insert a new firmware row and commit, so an auto-generated ID is assigned.

    `storage_path` is left unset until after the file is moved into its
    final, ID-scoped directory (see `_finalize_storage`), since the
    storage path depends on the database-assigned ID.

    Raises:
        HTTPException(500): if the database insert fails.
    """
    firmware = Firmware(
        filename=filename,
        file_hash=file_hash,
        file_size=file_size,
        status=FirmwareStatus.UPLOADED,
    )
    try:
        db.add(firmware)
        db.commit()
        db.refresh(firmware)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Database insertion failed for firmware '%s': %s", filename, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record firmware metadata.",
        ) from exc

    logger.info("Database insertion completed: firmware_id=%d, filename=%s", firmware.id, filename)
    return firmware


def _finalize_storage(db: Session, firmware: Firmware, temp_path: Path, filename: str) -> str:
    """Move the temp file into uploads/<firmware_id>/<filename> and record the path.

    Directories are created automatically. Because each firmware record
    has its own auto-generated ID, this location is always unique --
    an existing file is never overwritten.

    Raises:
        HTTPException(500): if the move fails or the storage_path update
            cannot be committed (the firmware row is left as-is; the
            temp file is preserved so no data is lost).
    """
    destination_dir = settings.UPLOAD_DIR / str(firmware.id)
    destination_path = destination_dir / filename

    try:
        destination_dir.mkdir(parents=True, exist_ok=True)
        if destination_path.exists():
            # Should be unreachable in practice (each firmware ID gets a
            # fresh directory), but never silently overwrite a file.
            raise FileExistsError(f"{destination_path} already exists.")
        shutil.move(str(temp_path), str(destination_path))
    except OSError as exc:
        logger.error(
            "Storage failure while finalizing firmware_id=%d: %s", firmware.id, exc
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store the uploaded firmware file.",
        ) from exc

    relative_path = str(Path(str(firmware.id)) / filename)
    try:
        firmware.storage_path = relative_path
        db.add(firmware)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error(
            "Database update of storage_path failed for firmware_id=%d: %s",
            firmware.id, exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to finalize firmware metadata.",
        ) from exc

    logger.info(
        "Storage location recorded: firmware_id=%d -> %s", firmware.id, relative_path
    )
    return relative_path


def handle_firmware_upload(
    upload_file: UploadFile, db: Session
) -> FirmwareUploadResponse | FirmwareDuplicateResponse:
    """Run the full firmware intake workflow for one uploaded file.

    Returns:
        `FirmwareUploadResponse` for a brand-new firmware upload, or
        `FirmwareDuplicateResponse` if a firmware with the same SHA-256
        hash was already uploaded previously.
    """
    logger.info("Upload request received: filename=%s", upload_file.filename)

    filename, _extension, _mime_type = validate_upload_metadata(upload_file.filename)
    logger.info("Validation completed for filename=%s", filename)

    temp_path, file_hash, file_size = _stream_to_temp_file_and_hash(upload_file.file)

    try:
        validate_not_empty(file_size)
        validate_max_size(file_size)
    except HTTPException:
        temp_path.unlink(missing_ok=True)
        raise

    existing_firmware = _find_existing_firmware_by_hash(db, file_hash)
    if existing_firmware is not None:
        logger.info(
            "Duplicate detection: firmware with hash %s already exists (firmware_id=%d).",
            file_hash, existing_firmware.id,
        )
        temp_path.unlink(missing_ok=True)
        return FirmwareDuplicateResponse(
            firmware_id=existing_firmware.id,
            sha256=existing_firmware.file_hash,
        )

    logger.info("Duplicate detection: no existing firmware found for hash %s.", file_hash)

    firmware = _create_firmware_record(db, filename, file_hash, file_size)
    _finalize_storage(db, firmware, temp_path, filename)

    logger.info("Upload completed: firmware_id=%d, filename=%s", firmware.id, filename)

    return FirmwareUploadResponse(
        firmware_id=firmware.id,
        filename=firmware.filename,
        file_hash=firmware.file_hash,
        file_size=firmware.file_size,
        status=firmware.status,
    )
