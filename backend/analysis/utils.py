"""
analysis/utils.py

Shared, reusable helper functions for the Firmware Analysis Engine:
entropy calculation, string extraction, file hashing, and safe file
operations. Every other `analysis/` module (and the Dataset Builder,
via `analysis.features`) uses these instead of re-implementing them, so
there is exactly one implementation of each.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Optional

try:
    import magic
except ImportError:  # pragma: no cover - optional at import time, checked at call time
    magic = None

logger = logging.getLogger("cryptosage.analysis.utils")

# Minimum length for a byte sequence to be counted as a printable string.
MIN_STRING_LENGTH = 4
_PRINTABLE_STRING_RE = re.compile(rb"[\x20-\x7e]{%d,}" % MIN_STRING_LENGTH)

# Chunk size used for all streaming file reads (hashing, copying).
CHUNK_SIZE_BYTES = 1024 * 1024


def shannon_entropy(data: bytes) -> Optional[float]:
    """Compute the Shannon entropy (bits per byte) of a byte buffer.

    Returns None if `data` is empty, since entropy is undefined there.
    """
    if not data:
        return None

    byte_counts = Counter(data)
    length = len(data)
    entropy = 0.0
    for count in byte_counts.values():
        probability = count / length
        entropy -= probability * math.log2(probability)
    return round(entropy, 6)


def extract_strings(data: bytes, min_length: int = MIN_STRING_LENGTH) -> list[str]:
    """Extract printable ASCII strings (length >= `min_length`) from raw bytes."""
    pattern = _PRINTABLE_STRING_RE if min_length == MIN_STRING_LENGTH else re.compile(
        rb"[\x20-\x7e]{%d,}" % min_length
    )
    try:
        return [match.decode("ascii", errors="ignore") for match in pattern.findall(data)]
    except Exception as exc:  # noqa: BLE001
        logger.warning("String extraction failed: %s", exc)
        return []


def count_strings(data: bytes, min_length: int = MIN_STRING_LENGTH) -> Optional[int]:
    """Count printable ASCII strings (length >= `min_length`) within raw bytes."""
    try:
        pattern = _PRINTABLE_STRING_RE if min_length == MIN_STRING_LENGTH else re.compile(
            rb"[\x20-\x7e]{%d,}" % min_length
        )
        return len(pattern.findall(data))
    except Exception as exc:  # noqa: BLE001
        logger.warning("String counting failed: %s", exc)
        return None


def sha256_file(path: Path, chunk_size: int = CHUNK_SIZE_BYTES) -> Optional[str]:
    """Compute the SHA-256 hex digest of a file, streaming it in chunks.

    Never loads the whole file into memory -- safe for firmware images
    well over 500 MB. Returns None (and logs) if the file cannot be read.
    """
    sha256 = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(chunk_size)
                if not chunk:
                    break
                sha256.update(chunk)
        return sha256.hexdigest()
    except OSError as exc:
        logger.error("Could not hash file %s: %s", path, exc)
        return None


def safe_read_bytes(path: Path, max_bytes: Optional[int] = None) -> Optional[bytes]:
    """Read a file's contents, never raising on failure.

    Args:
        path: File to read.
        max_bytes: If set, only the first `max_bytes` bytes are read
            (useful for very large firmware images when only a bounded
            sample is needed, e.g. for entropy estimation).

    Returns:
        The file's bytes, or None if the file could not be read.
    """
    try:
        with path.open("rb") as handle:
            return handle.read(max_bytes) if max_bytes else handle.read()
    except OSError as exc:
        logger.error("Could not read file %s: %s", path, exc)
        return None


def safe_make_directory(path: Path) -> bool:
    """Create a directory (and parents) if it doesn't already exist.

    Returns True on success (or if it already existed), False if
    creation failed for a permissions or other OS-level reason.
    """
    try:
        path.mkdir(parents=True, exist_ok=True)
        return True
    except OSError as exc:
        logger.error("Could not create directory %s: %s", path, exc)
        return False


def safe_copy_file(source: Path, destination: Path) -> bool:
    """Copy a file, creating the destination directory if needed.

    Never overwrites an existing destination file. Returns True on
    success, False on any failure (logged).
    """
    try:
        if destination.exists():
            logger.warning("Refusing to overwrite existing file at %s", destination)
            return False
        safe_make_directory(destination.parent)
        shutil.copy2(source, destination)
        return True
    except OSError as exc:
        logger.error("Could not copy %s -> %s: %s", source, destination, exc)
        return False


def guess_mime_type(path: Path) -> Optional[str]:
    """Guess a file's MIME type from its content using `python-magic`.

    Content-based (not extension-based), so it correctly identifies a
    file's real type even if it has been renamed or has no extension.
    Returns None if `python-magic`/libmagic is unavailable or the file
    can't be inspected -- never raises.
    """
    if magic is None:
        logger.debug("python-magic is not installed; MIME-type detection skipped.")
        return None
    try:
        return magic.from_file(str(path), mime=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not determine MIME type for %s: %s", path, exc)
        return None


def relative_to_safe(path: Path, base: Path) -> str:
    """Return `path` relative to `base` as a string, falling back to the
    absolute path if `path` is not actually under `base`.
    """
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)
