
"""
Core firmware upload logic.

Streams uploaded firmware to a temporary file, calculates its SHA-256 hash,
checks for duplicates, records new firmware, and moves the file to its
firmware-ID-scoped storage directory.
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

_CHUNK_SIZE_BYTES = 1024 * 1024


def _temp_upload_path() -> Path:
    """Create a unique temporary upload path."""
    temp_dir = settings.UPLOAD_DIR / ".tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir / f"{uuid.uuid4().hex}.part"


def _stream_to_temp_file_and_hash(
    source: BinaryIO,
) -> tuple[Path, str, int]:
    """Stream and hash the upload without loading it fully into memory."""
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
                        "Upload aborted: exceeded maximum size of %d bytes.",
                        max_bytes,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=(
                            "Firmware file exceeds the maximum allowed size of "
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
        logger.error("Storage failure while streaming upload: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store the uploaded firmware file.",
        ) from exc
    except Exception as exc:
        temp_path.unlink(missing_ok=True)
        logger.exception("Unexpected failure while reading uploaded firmware.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process the uploaded firmware file.",
        ) from exc

    logger.info(
        "Upload streamed: %d bytes; SHA-256 generated.",
        total_bytes,
    )
    return temp_path, sha256.hexdigest(), total_bytes


def _find_existing_firmware_by_hash(
    db: Session,
    file_hash: str,
) -> Firmware | None:
    """Find a firmware record with the same SHA-256 hash."""
    return (
        db.query(Firmware)
        .filter(Firmware.file_hash == file_hash)
        .first()
    )


def _create_firmware_record(
    db: Session,
    filename: str,
    file_hash: str,
    file_size: int,
) -> Firmware:
    """Create and commit the database row for a new firmware upload."""
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
        logger.error(
            "Database insertion failed for firmware '%s'.",
            filename,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record firmware metadata.",
        ) from exc

    logger.info(
        "Firmware record created: firmware_id=%d, filename=%s",
        firmware.id,
        filename,
    )
    return firmware


def _finalize_storage(
    db: Session,
    firmware: Firmware,
    temp_path: Path,
    filename: str,
) -> str:
    """Move the upload into its firmware-specific directory and save its path."""
    destination_dir = settings.UPLOAD_DIR / str(firmware.id)
    destination_path = destination_dir / filename

    try:
        destination_dir.mkdir(parents=True, exist_ok=True)

        if destination_path.exists():
            raise FileExistsError(
                f"Refusing to overwrite existing file: {destination_path}"
            )

        shutil.move(str(temp_path), str(destination_path))

    except OSError as exc:
        logger.error(
            "Storage finalization failed for firmware_id=%d.",
            firmware.id,
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
            "Storage path database update failed for firmware_id=%d.",
            firmware.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to finalize firmware metadata.",
        ) from exc

    logger.info(
        "Storage location recorded for firmware_id=%d.",
        firmware.id,
    )
    return relative_path


def handle_firmware_upload(
    upload_file: UploadFile,
    db: Session,
) -> FirmwareUploadResponse | FirmwareDuplicateResponse:
    """Validate, stream, deduplicate, and store one firmware upload."""
    logger.info("Upload request received: filename=%s", upload_file.filename)

    filename, _extension, _mime_type = validate_upload_metadata(
        upload_file.filename
    )

    temp_path, file_hash, file_size = _stream_to_temp_file_and_hash(
        upload_file.file
    )

    # This finally block cleans up temporary files on validation, database,
    # duplicate, or finalization failures. If the file has already been moved,
    # the temporary path no longer exists and unlink(missing_ok=True) is safe.
    try:
        validate_not_empty(file_size)
        validate_max_size(file_size)

        existing_firmware = _find_existing_firmware_by_hash(db, file_hash)
        if existing_firmware is not None:
            logger.info(
                "Duplicate firmware detected: firmware_id=%d.",
                existing_firmware.id,
            )
            return FirmwareDuplicateResponse(
                firmware_id=existing_firmware.id,
                sha256=existing_firmware.file_hash,
            )

        firmware = _create_firmware_record(
            db,
            filename,
            file_hash,
            file_size,
        )

        _finalize_storage(db, firmware, temp_path, filename)

        logger.info(
            "Upload completed: firmware_id=%d, filename=%s",
            firmware.id,
            filename,
        )

        return FirmwareUploadResponse(
            firmware_id=firmware.id,
            filename=firmware.filename,
            file_hash=firmware.file_hash,
            file_size=firmware.file_size,
            status=firmware.status,
        )

    finally:
        temp_path.unlink(missing_ok=True)
