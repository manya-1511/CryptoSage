
"""
Validates incoming firmware uploads before they are stored or recorded
in the database.

All validation functions are side-effect free and can be unit tested
independently.
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
    """Validate that a filename is present and contains no path components."""
    if not filename or not filename.strip():
        logger.warning("Upload rejected: no filename provided.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No firmware file was provided.",
        )

    filename = filename.strip()

    if (
        filename in {".", ".."}
        or "/" in filename
        or "\\" in filename
        or "\x00" in filename
        or Path(filename).name != filename
    ):
        logger.warning("Upload rejected: unsafe filename.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid firmware filename.",
        )

    return filename


def validate_extension(filename: str) -> str:
    """Ensure the upload extension is in the configured allow-list."""
    extension = Path(filename).suffix.lower()

    if extension not in settings.ALLOWED_FIRMWARE_EXTENSIONS:
        logger.warning(
            "Upload rejected: unsupported extension '%s'.",
            extension,
        )
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported firmware format.",
        )

    return extension


def validate_mime_type(filename: str) -> str | None:
    """Validate the inferred MIME type when one is available."""
    guessed_type, _ = mimetypes.guess_type(filename)

    # Firmware extensions often have no registered MIME type. Unknown
    # MIME types remain accepted for compatibility with existing uploads.
    if (
        guessed_type is not None
        and guessed_type not in settings.ALLOWED_FIRMWARE_MIME_TYPES
    ):
        logger.warning(
            "Upload rejected: disallowed MIME type '%s'.",
            guessed_type,
        )
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported firmware MIME type.",
        )

    return guessed_type


def validate_not_empty(file_size: int) -> None:
    """Reject an empty firmware file."""
    if file_size <= 0:
        logger.warning("Upload rejected: empty file.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded firmware file is empty.",
        )


def validate_max_size(file_size: int) -> None:
    """Reject files that exceed the configured upload limit."""
    max_bytes = settings.max_upload_size_bytes

    if file_size > max_bytes:
        logger.warning(
            "Upload rejected: %d bytes exceeds the %d-byte limit.",
            file_size,
            max_bytes,
        )
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                "Firmware file exceeds the maximum allowed size of "
                f"{settings.MAX_UPLOAD_SIZE_MB} MB."
            ),
        )


def validate_upload_metadata(
    filename: str | None,
) -> tuple[str, str, str | None]:
    """Validate upload filename, extension, and inferred MIME type."""
    validated_filename = validate_filename_present(filename)
    extension = validate_extension(validated_filename)
    mime_type = validate_mime_type(validated_filename)

    return validated_filename, extension, mime_type
