"""
analysis/firmware.py

Firmware extraction entry point for the Firmware Analysis Engine.

Uses Binwalk to extract a firmware image's embedded filesystem(s) and
files into `analysis_output/<firmware_id>/`, so `analysis.binary`'s
discovery step has a directory tree to search for executables. Handles
`.bin`, `.img`, and `.elf` uploads; extraction failures are handled
gracefully -- a meaningful result is always returned, and the original
firmware file is always made available for analysis even if Binwalk
finds nothing to extract (e.g. a raw, non-filesystem firmware blob, or
an already-standalone `.elf` binary).
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

# Extensions this module knows how to handle. Kept in sync with the
# Phase 3 upload module's allow-list, though intentionally not imported
# from there, to keep the analysis engine independently reusable.
SUPPORTED_FIRMWARE_EXTENSIONS: set[str] = {".bin", ".img", ".elf"}

# Timeout for the Binwalk subprocess, so a pathological/huge firmware
# image can never hang the pipeline indefinitely.
EXTRACTION_TIMEOUT_SECONDS = 900


@dataclass
class ExtractionResult:
    """Outcome of attempting to extract one firmware image.

    `success` reflects whether Binwalk itself ran and completed
    normally -- not necessarily whether it found anything to extract
    (a raw firmware blob with no embedded filesystem is not a failure).
    `output_dir` is always populated (even on failure) as long as a
    directory could be created, since the original firmware file is
    always copied there for downstream analysis.
    """

    success: bool
    output_dir: Optional[Path]
    message: str


def _binwalk_available() -> bool:
    """Check whether the Binwalk CLI is installed on this system."""
    return shutil.which("binwalk") is not None


def extract_firmware(
    firmware_path: Path,
    firmware_id: int | str,
    output_root: Path,
) -> ExtractionResult:
    """Extract a firmware image with Binwalk into `output_root/<firmware_id>/`.

    Args:
        firmware_path: Path to the uploaded firmware file (`.bin`,
            `.img`, or `.elf`).
        firmware_id: The firmware's database ID (or any unique
            identifier), used to scope the extraction output directory.
        output_root: Base directory under which
            `<firmware_id>/` is created (e.g. `analysis_output/`).

    Returns:
        An `ExtractionResult`. This function never raises for expected
        failure modes (missing Binwalk, extraction errors, timeouts) --
        every failure is logged and reflected in the returned result,
        so a single firmware's extraction failure never terminates the
        application or blocks processing of other firmware.
    """
    firmware_path = Path(firmware_path)
    extension = firmware_path.suffix.lower()

    if extension not in SUPPORTED_FIRMWARE_EXTENSIONS:
        message = f"Unsupported firmware extension '{extension}' for extraction."
        logger.error(message)
        return ExtractionResult(success=False, output_dir=None, message=message)

    if not firmware_path.exists():
        message = f"Firmware file not found: {firmware_path}"
        logger.error(message)
        return ExtractionResult(success=False, output_dir=None, message=message)

    output_dir = output_root / str(firmware_id)
    if not safe_make_directory(output_dir):
        message = f"Could not create extraction output directory: {output_dir}"
        logger.error(message)
        return ExtractionResult(success=False, output_dir=None, message=message)

    logger.info("Extraction started: firmware_id=%s, file=%s", firmware_id, firmware_path.name)

    binwalk_ok = True
    binwalk_message = ""

    if not _binwalk_available():
        binwalk_ok = False
        binwalk_message = "Binwalk is not installed; skipping automated extraction."
        logger.warning(binwalk_message)
    else:
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
            )
            if result.returncode != 0:
                binwalk_ok = False
                binwalk_message = (result.stderr or result.stdout or "unknown Binwalk error")[-1000:]
                logger.warning(
                    "Binwalk exited with code %d for firmware_id=%s: %s",
                    result.returncode, firmware_id, binwalk_message,
                )
            else:
                logger.info("Binwalk extraction completed for firmware_id=%s", firmware_id)
        except subprocess.TimeoutExpired:
            binwalk_ok = False
            binwalk_message = f"Binwalk extraction timed out after {EXTRACTION_TIMEOUT_SECONDS}s"
            logger.error(binwalk_message)
        except OSError as exc:
            binwalk_ok = False
            binwalk_message = str(exc)
            logger.error("Binwalk failed to run for firmware_id=%s: %s", firmware_id, exc)

    # Always make the original firmware file available under the output
    # directory too -- Binwalk may legitimately find nothing to carve
    # out (a raw, non-filesystem image, or an already-standalone .elf),
    # and downstream binary discovery should still have something to
    # examine rather than an empty directory.
    original_copy_dir = output_dir / "original"
    original_destination = original_copy_dir / firmware_path.name
    if not original_destination.exists():
        copied = safe_copy_file(firmware_path, original_destination)
        if not copied:
            logger.warning(
                "Could not copy original firmware into extraction output for firmware_id=%s",
                firmware_id,
            )

    if binwalk_ok:
        return ExtractionResult(
            success=True,
            output_dir=output_dir,
            message="Extraction completed successfully.",
        )

    # Binwalk failed or is unavailable, but the original file is still
    # in place for analysis -- report a meaningful, non-fatal error.
    return ExtractionResult(
        success=False,
        output_dir=output_dir,
        message=f"Automated extraction did not complete: {binwalk_message}",
    )
