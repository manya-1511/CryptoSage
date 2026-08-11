"""
input/validator.py

Validates incoming firmware uploads before they are stored or recorded
in the database (Phase 3 -- Firmware Input Module).

Every check here is deliberately independent and side-effect free (no
disk or database access) so it can be unit tested in isolation and
reused by future phases without modification.
"""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path

from fastapi import HTTPException, status

from config import get_settings

logger = logging.getLogger("cryptosage.input.validator")

settings = get_settings()


def validate_filename_present(filename: str | None) -> str:
    """Ensure a filename was actually provided.

    Raises:
        HTTPException(400): if `filename` is missing or blank.

    Returns:
        The validated, non-empty filename.
    """
    if not filename or not filename.strip():
        logger.warning("Upload rejected: no filename provided.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No firmware file was provided.",
        )
    return filename


def validate_extension(filename: str) -> str:
    """Ensure the upload's extension is in the configured allow-list.

    The allow-list comes from `config.Settings.ALLOWED_FIRMWARE_EXTENSIONS`
    (configurable via the `ALLOWED_FIRMWARE_EXTENSIONS` environment
    variable) rather than being hardcoded here.

    Raises:
        HTTPException(415): if the extension is not supported.

    Returns:
        The validated, lowercased extension (e.g. ".bin").
    """
    extension = Path(filename).suffix.lower()
    if extension not in settings.ALLOWED_FIRMWARE_EXTENSIONS:
        logger.warning(
            "Upload rejected: unsupported extension '%s' for file '%s'.",
            extension, filename,
        )
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported firmware format.",
        )
    return extension


def validate_mime_type(filename: str) -> str | None:
    """Best-effort MIME type validation based on filename.

    Firmware extensions such as `.bin`, `.img`, and `.elf` are not
    registered with Python's standard `mimetypes` database, so
    `mimetypes.guess_type` legitimately returns `None` for them -- this
    is expected and accepted. If a MIME type *is* guessed, it must be in
    the configured allow-list (`ALLOWED_FIRMWARE_MIME_TYPES`).

    Raises:
        HTTPException(415): if a MIME type was guessed and it is not
            in the allow-list.

    Returns:
        The guessed MIME type, or None if it could not be determined.
    """
    guessed_type, _ = mimetypes.guess_type(filename)
    if guessed_type is not None and guessed_type not in settings.ALLOWED_FIRMWARE_MIME_TYPES:
        logger.warning(
            "Upload rejected: MIME type '%s' for file '%s' is not permitted.",
            guessed_type, filename,
        )
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported firmware MIME type.",
        )
    return guessed_type


def validate_not_empty(file_size: int) -> None:
    """Ensure the uploaded file actually contains data.

    Raises:
        HTTPException(400): if `file_size` is zero.
    """
    if file_size <= 0:
        logger.warning("Upload rejected: empty file (0 bytes).")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded firmware file is empty.",
        )


def validate_max_size(file_size: int) -> None:
    """Ensure the uploaded file does not exceed the configured size limit.

    Raises:
        HTTPException(413): if `file_size` exceeds
            `settings.max_upload_size_bytes`.
    """
    max_bytes = settings.max_upload_size_bytes
    if file_size > max_bytes:
        logger.warning(
            "Upload rejected: file size %d bytes exceeds maximum of %d bytes.",
            file_size, max_bytes,
        )
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"Firmware file exceeds the maximum allowed size of "
                f"{settings.MAX_UPLOAD_SIZE_MB} MB."
            ),
        )


def validate_upload_metadata(filename: str | None) -> tuple[str, str, str | None]:
    """Run all filename/extension/MIME checks that don't require file bytes.

    This is intentionally split from size-based validation
    (`validate_not_empty`, `validate_max_size`) so callers can validate
    metadata immediately, before streaming the file to disk.

    Returns:
        A tuple of (filename, extension, guessed_mime_type).
    """
    validated_filename = validate_filename_present(filename)
    extension = validate_extension(validated_filename)
    mime_type = validate_mime_type(validated_filename)
    return validated_filename, extension, mime_type
