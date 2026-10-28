
"""
analysis/firmware.py

Isolated firmware extraction for the CryptoSage analysis engine.

The caller should provide a unique output_root for each analysis run.
The extraction directory is output_root/<firmware_id>/.

The uploaded source file is never modified or deleted. A copy is placed
under <output_dir>/original/ so a standalone ELF or raw firmware image
can still be considered by the analysis pipeline.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from analysis.utils import safe_copy_file, safe_make_directory

logger = logging.getLogger("cryptosage.analysis.firmware")

SUPPORTED_FIRMWARE_EXTENSIONS: set[str] = {".bin", ".img", ".elf"}
EXTRACTION_TIMEOUT_SECONDS = 900


@dataclass
class ExtractionResult:
    """Outcome of a single firmware extraction attempt."""

    success: bool
    output_dir: Optional[Path]
    message: str


def _binwalk_available() -> bool:
    """Return whether the Binwalk CLI is available."""
    return shutil.which("binwalk") is not None


def extract_firmware(
    firmware_path: Path,
    firmware_id: int | str,
    output_root: Path,
) -> ExtractionResult:
    """
    Extract one firmware image into output_root/<firmware_id>/.

    IMPORTANT:
        output_root must be unique to the current run. This prevents
        files left by an earlier attempt from being treated as fresh
        extraction output.

    Expected extraction failures are returned as ExtractionResult
    values instead of being raised to the API layer.
    """
    firmware_path = Path(firmware_path)
    output_root = Path(output_root)

    extension = firmware_path.suffix.lower()

    if extension not in SUPPORTED_FIRMWARE_EXTENSIONS:
        message = f"Unsupported firmware extension '{extension}'."
        logger.error(
            "%s firmware_id=%s",
            message,
            firmware_id,
        )
        return ExtractionResult(
            success=False,
            output_dir=None,
            message=message,
        )

    if not firmware_path.is_file():
        message = "Firmware source file does not exist or is not a file."
        logger.error(
            "%s firmware_id=%s",
            message,
            firmware_id,
        )
        return ExtractionResult(
            success=False,
            output_dir=None,
            message=message,
        )

    output_dir = output_root / str(firmware_id)

    if not safe_make_directory(output_dir):
        message = "Could not create the isolated extraction directory."
        logger.error(
            "%s firmware_id=%s",
            message,
            firmware_id,
        )
        return ExtractionResult(
            success=False,
            output_dir=None,
            message=message,
        )

    logger.info(
        "Starting firmware extraction: firmware_id=%s, source=%s",
        firmware_id,
        firmware_path.name,
    )

    # Copy the original into the isolated run directory before invoking
    # Binwalk. This copy is separate from the uploaded source file.
    original_copy_dir = output_dir / "original"
    original_destination = original_copy_dir / firmware_path.name

    if not safe_make_directory(original_copy_dir):
        message = "Could not create the original-firmware copy directory."
        logger.error(
            "%s firmware_id=%s",
            message,
            firmware_id,
        )
        return ExtractionResult(
            success=False,
            output_dir=output_dir,
            message=message,
        )

    if not safe_copy_file(firmware_path, original_destination):
        message = "Could not copy the original firmware into the run directory."
        logger.error(
            "%s firmware_id=%s",
            message,
            firmware_id,
        )
        return ExtractionResult(
            success=False,
            output_dir=output_dir,
            message=message,
        )

    if not _binwalk_available():
        message = "Binwalk is not installed; only the original firmware copy is available."
        logger.warning(
            "%s firmware_id=%s",
            message,
            firmware_id,
        )
        return ExtractionResult(
            success=False,
            output_dir=output_dir,
            message=message,
        )

    try:
        result = subprocess.run(
            [
                "binwalk",
                "--extract",
                "--directory",
                str(output_dir),
                str(firmware_path),
            ],
            capture_output=True,
            text=True,
            timeout=EXTRACTION_TIMEOUT_SECONDS,
            check=False,
        )

        if result.returncode != 0:
            detail = (
                result.stderr
                or result.stdout
                or "Binwalk returned a non-zero exit code."
            )[-1000:]

            message = f"Binwalk extraction failed: {detail}"
            logger.warning(
                "Binwalk failed for firmware_id=%s, exit_code=%d: %s",
                firmware_id,
                result.returncode,
                detail,
            )
            return ExtractionResult(
                success=False,
                output_dir=output_dir,
                message=message,
            )

        logger.info(
            "Binwalk extraction completed: firmware_id=%s",
            firmware_id,
        )

        return ExtractionResult(
            success=True,
            output_dir=output_dir,
            message="Binwalk extraction completed successfully.",
        )

    except subprocess.TimeoutExpired:
        message = (
            "Binwalk extraction timed out after "
            f"{EXTRACTION_TIMEOUT_SECONDS} seconds."
        )
        logger.error(
            "%s firmware_id=%s",
            message,
            firmware_id,
        )
        return ExtractionResult(
            success=False,
            output_dir=output_dir,
            message=message,
        )

    except OSError:
        # Avoid exposing local filesystem details in API-facing messages.
        logger.exception(
            "Could not execute Binwalk for firmware_id=%s",
            firmware_id,
        )
        return ExtractionResult(
            success=False,
            output_dir=output_dir,
            message="Binwalk could not be executed.",
        )
