"""
analysis/binary.py

Binary discovery and ELF parsing for the Firmware Analysis Engine.

Two responsibilities:

1. `discover_binaries()` -- recursively walk an extracted firmware
   filesystem (or a directory of compiled libraries, for the Dataset
   Builder) and return every real ELF executable/shared library found,
   ignoring images, fonts, configs, documentation, and temporary files.
2. `parse_elf()` -- parse a single discovered binary with LIEF and
   return structured metadata: architecture, entry point, sections,
   segments, imports, exports, symbols, size, bitness, endianness, and
   hashes.

Both are static-only (no execution of any discovered binary).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

try:
    import lief
except ImportError:  # pragma: no cover - dependency is required at runtime
    lief = None

from analysis.utils import guess_mime_type, safe_read_bytes, sha256_file

logger = logging.getLogger("cryptosage.analysis.binary")

# ELF magic bytes used to positively identify a compiled binary.
ELF_MAGIC = b"\x7fELF"

# MIME type prefixes/values that positively identify non-executable
# content (images, fonts, documents, text/config data) even if a file
# has been renamed or has no extension. Checked via `python-magic`
# (content-based), in addition to the extension-based checks below, so
# discovery is robust to misleading filenames.
IGNORED_MIME_PREFIXES: tuple[str, ...] = ("image/", "font/", "text/")
IGNORED_MIME_TYPES: set[str] = {
    "application/pdf", "application/json", "application/xml",
    "application/x-font-ttf", "application/vnd.ms-fontobject",
}

# Directory name fragments that mark non-executable content -- never
# worth treating as candidate binaries.
IGNORED_DIR_KEYWORDS: list[str] = [
    "doc", "docs", "test", "tests", "example", "examples",
    "sample", "samples", "demo", "demos", ".git",
]

# File extensions that are never binaries of interest: images, fonts,
# configuration/data files, documentation, and temporary/build
# artifacts (per the Phase 4 spec's explicit ignore list). Object files
# (.o) and static archives (.a) are intentionally NOT excluded here --
# they are valid ELF content and may legitimately appear inside an
# extracted firmware filesystem.
IGNORED_EXTENSIONS: set[str] = {
    # Images
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg", ".webp", ".tiff",
    # Fonts
    ".ttf", ".otf", ".woff", ".woff2", ".eot",
    # Configuration / data
    ".conf", ".cfg", ".ini", ".json", ".xml", ".yaml", ".yml", ".csv",
    # Documentation
    ".md", ".txt", ".pdf", ".html", ".htm", ".rst",
    # Temporary files
    ".tmp", ".bak", ".log",
}


def _is_ignored_path(relative_path: Path) -> bool:
    """Return True if any path component matches an ignored-directory keyword."""
    lowered_parts = [part.lower() for part in relative_path.parts]
    return any(
        keyword in part
        for part in lowered_parts
        for keyword in IGNORED_DIR_KEYWORDS
    )


def _is_elf_binary(path: Path) -> bool:
    """Check the ELF magic bytes to positively identify a compiled binary.

    Also consults `python-magic` (content-based MIME type) to reject
    files that merely lack a recognized extension but are clearly
    non-executable content (images, fonts, text/config data) --
    stronger than an extension check alone, since it can't be fooled by
    a misleading filename.
    """
    if path.suffix.lower() in IGNORED_EXTENSIONS:
        return False

    try:
        with path.open("rb") as handle:
            if handle.read(4) != ELF_MAGIC:
                return False
    except OSError:
        return False

    mime_type = guess_mime_type(path)
    if mime_type is not None:
        if mime_type in IGNORED_MIME_TYPES or mime_type.startswith(IGNORED_MIME_PREFIXES):
            logger.debug("Rejecting %s: MIME type '%s' is non-executable content.", path, mime_type)
            return False

    return True


def discover_binaries(root_dir: Path) -> list[Path]:
    """Recursively discover every valid ELF binary/shared library under `root_dir`.

    Ignores images, fonts, configs, documentation, temporary files, and
    anything under a test/example/doc directory. Never raises -- a
    directory that can't be walked simply yields no results (logged).

    Args:
        root_dir: Directory to search (e.g. an extracted firmware
            filesystem, or a directory of compiled libraries).

    Returns:
        A list of paths to discovered ELF binaries/shared libraries.
    """
    discovered: list[Path] = []
    if not root_dir.exists():
        logger.warning("Binary discovery root does not exist: %s", root_dir)
        return discovered

    try:
        for path in root_dir.rglob("*"):
            if not path.is_file() or path.is_symlink():
                continue
            try:
                relative = path.relative_to(root_dir)
            except ValueError:
                relative = path
            if _is_ignored_path(relative):
                continue
            if _is_elf_binary(path):
                discovered.append(path)
    except OSError as exc:
        logger.error("Error while walking %s for binaries: %s", root_dir, exc)

    logger.info("Discovered %d candidate binaries under %s", len(discovered), root_dir)
    return discovered


def _normalize_architecture(binary: "lief.Binary") -> Optional[str]:
    """Map a LIEF-parsed binary's header info to a canonical architecture name."""
    try:
        machine_type = str(binary.header.machine_type).upper()
    except Exception:  # noqa: BLE001
        return None

    if "X86_64" in machine_type or "AMD64" in machine_type:
        return "x86_64"
    if "AARCH64" in machine_type or "ARM64" in machine_type:
        return "arm64"
    if "ARM" in machine_type:
        return "arm"
    if "MIPS" in machine_type:
        return "mips"
    if "I386" in machine_type or "386" in machine_type:
        return "x86"
    return machine_type or None


def parse_elf(binary_path: Path) -> Optional[dict[str, Any]]:
    """Parse a single ELF binary with LIEF and return structured metadata.

    Never raises: any parsing failure is logged and results in `None`,
    so a single unparseable binary never stops a batch of others from
    being processed.

    Returns a dict with keys: `path`, `binary_size`, `sha256`,
    `architecture`, `bitness`, `endianness`, `entry_point`, `file_type`,
    `sections` (list of {name, size, entropy, virtual_address}),
    `segments` (list of {type, virtual_address, size}), `imported_libraries`,
    `imported_functions`, `exported_functions`, `symbols` (count and names),
    `section_count`, `segment_count`, `import_count`, `export_count`,
    `symbol_count`.
    """
    if lief is None:
        logger.error("LIEF is not installed; cannot parse %s", binary_path)
        return None

    raw_bytes = safe_read_bytes(binary_path)
    if raw_bytes is None:
        return None

    try:
        binary = lief.parse(str(binary_path))
    except Exception as exc:  # noqa: BLE001
        logger.warning("LIEF failed to parse %s: %s", binary_path, exc)
        return None

    if binary is None:
        logger.warning("LIEF returned no result for %s", binary_path)
        return None

    from analysis.utils import shannon_entropy  # local import avoids cycle at module load

    metadata: dict[str, Any] = {
        "path": str(binary_path),
        "binary_size": len(raw_bytes),
        "sha256": sha256_file(binary_path),
        "architecture": _normalize_architecture(binary),
        "bitness": None,
        "endianness": None,
        "entry_point": None,
        "file_type": None,
        "sections": [],
        "segments": [],
        "imported_libraries": [],
        "imported_functions": [],
        "exported_functions": [],
        "symbols": [],
        "section_count": None,
        "segment_count": None,
        "import_count": None,
        "export_count": None,
        "symbol_count": None,
    }

    try:
        metadata["bitness"] = 64 if binary.header.identity_class == lief.ELF.ELF_CLASS.CLASS64 else 32
    except Exception:  # noqa: BLE001
        pass

    try:
        metadata["endianness"] = (
            "little" if binary.header.identity_data == lief.ELF.ELF_DATA.LSB else "big"
        )
    except Exception:  # noqa: BLE001
        pass

    try:
        metadata["entry_point"] = int(binary.entrypoint)
    except Exception:  # noqa: BLE001
        pass

    try:
        metadata["file_type"] = str(binary.header.file_type)
    except Exception:  # noqa: BLE001
        pass

    try:
        sections = []
        for section in binary.sections:
            try:
                content = bytes(section.content)
            except Exception:  # noqa: BLE001
                content = b""
            sections.append({
                "name": section.name,
                "size": int(section.size),
                "virtual_address": int(section.virtual_address),
                "entropy": shannon_entropy(content) if content else None,
            })
        metadata["sections"] = sections
        metadata["section_count"] = len(sections)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Section parsing failed for %s: %s", binary_path, exc)

    try:
        segments = [
            {
                "type": str(segment.type),
                "virtual_address": int(segment.virtual_address),
                "size": int(segment.physical_size),
            }
            for segment in binary.segments
        ]
        metadata["segments"] = segments
        metadata["segment_count"] = len(segments)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Segment parsing failed for %s: %s", binary_path, exc)

    try:
        imported_libraries = list(binary.libraries)
        imported_functions = [
            getattr(imported, "name", None) or str(imported)
            for imported in binary.imported_functions
        ]
        metadata["imported_libraries"] = imported_libraries
        metadata["imported_functions"] = imported_functions
        metadata["import_count"] = len(imported_libraries) + len(imported_functions)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Import parsing failed for %s: %s", binary_path, exc)

    try:
        exported_functions = [
            getattr(exported, "name", None) or str(exported)
            for exported in binary.exported_functions
        ]
        metadata["exported_functions"] = exported_functions
        metadata["export_count"] = len(exported_functions)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Export parsing failed for %s: %s", binary_path, exc)

    try:
        symbol_names = [getattr(symbol, "name", None) for symbol in binary.symbols]
        symbol_names = [name for name in symbol_names if name]
        metadata["symbols"] = symbol_names
        metadata["symbol_count"] = len(symbol_names)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Symbol parsing failed for %s: %s", binary_path, exc)

    return metadata
