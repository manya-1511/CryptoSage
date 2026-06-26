import hashlib
import os
import magic
import struct
import logging
from pathlib import Path
from typing import Tuple, Optional, Dict, Any

from app.core.config import settings

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".bin", ".img", ".elf", ".hex"}

ELF_MAGIC = b"\x7fELF"
ELF_ARCH_MAP = {
    0x03: "x86",
    0x28: "ARM",
    0x3E: "x86-64",
    0xB7: "AArch64",
    0x08: "MIPS",
    0xF3: "RISC-V",
    0x14: "PowerPC",
}
ELF_ENDIAN_MAP = {1: "little", 2: "big"}

INTEL_HEX_RECORD_TYPES = {0, 1, 2, 3, 4, 5}


def compute_hashes(file_path: str) -> Tuple[str, str]:
    sha256 = hashlib.sha256()
    md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
            md5.update(chunk)
    return sha256.hexdigest(), md5.hexdigest()


def detect_mime_type(file_path: str) -> str:
    try:
        mime = magic.from_file(file_path, mime=True)
        return mime
    except Exception:
        return "application/octet-stream"


def parse_elf_header(file_path: str) -> Dict[str, Any]:
    info: Dict[str, Any] = {}
    try:
        with open(file_path, "rb") as f:
            header = f.read(64)
        if len(header) < 16:
            return info
        if header[:4] != ELF_MAGIC:
            return info
        endian_byte = header[5]
        arch_byte = struct.unpack_from("<H", header, 18)[0] if endian_byte == 1 else struct.unpack_from(">H", header, 18)[0]
        info["architecture"] = ELF_ARCH_MAP.get(arch_byte, f"Unknown (0x{arch_byte:02X})")
        info["endianness"] = ELF_ENDIAN_MAP.get(endian_byte, "unknown")
        info["elf_class"] = "ELF32" if header[4] == 1 else "ELF64"
    except Exception as e:
        logger.warning(f"ELF parse failed: {e}")
    return info


def is_valid_intel_hex(file_path: str) -> bool:
    try:
        with open(file_path, "r", errors="ignore") as f:
            lines = [l.strip() for l in f.readlines()[:20]]
        if not lines:
            return False
        return all(line.startswith(":") and len(line) >= 11 for line in lines if line)
    except Exception:
        return False


def validate_firmware_file(
    file_path: str,
    original_filename: str,
    file_size: int,
) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Returns (is_valid, error_message, metadata_dict)
    """
    metadata: Dict[str, Any] = {}

    # 1. Size check
    if file_size == 0:
        return False, "File is empty.", metadata
    if file_size > settings.max_file_size_bytes:
        return False, f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB} MB.", metadata

    # 2. Extension check
    ext = Path(original_filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return False, f"Unsupported file extension '{ext}'. Allowed: {', '.join(SUPPORTED_EXTENSIONS)}.", metadata

    metadata["file_extension"] = ext

    # 3. MIME type detection
    mime = detect_mime_type(file_path)
    metadata["mime_type"] = mime

    # 4. Format-specific validation
    if ext == ".elf":
        with open(file_path, "rb") as f:
            magic_bytes = f.read(4)
        if magic_bytes != ELF_MAGIC:
            return False, "File has .elf extension but is not a valid ELF binary.", metadata
        elf_info = parse_elf_header(file_path)
        metadata.update(elf_info)

    elif ext == ".hex":
        if not is_valid_intel_hex(file_path):
            return False, "File has .hex extension but does not appear to be valid Intel HEX format.", metadata

    # .bin and .img: accept any content (firmware blobs)

    return True, None, metadata