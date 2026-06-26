import asyncio
import json
import logging
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _run_binwalk_scan(file_path: str) -> List[Dict[str, Any]]:
    """Run binwalk signature scan and return parsed results."""
    results = []
    try:
        proc = subprocess.run(
            ["binwalk", "--log=/dev/stdout", file_path],
            capture_output=True,
            text=True,
            timeout=300,
        )
        lines = proc.stdout.splitlines()
        in_table = False
        for line in lines:
            line = line.strip()
            if line.startswith("DECIMAL") or line.startswith("---"):
                in_table = True
                continue
            if not in_table or not line:
                continue
            parts = line.split(None, 2)
            if len(parts) < 3:
                continue
            try:
                results.append({
                    "offset": int(parts[0]),
                    "hex_offset": parts[1],
                    "description": parts[2],
                })
            except ValueError:
                continue
    except FileNotFoundError:
        logger.warning("binwalk not found — returning mock scan data for development")
        results = _mock_scan_results(file_path)
    except subprocess.TimeoutExpired:
        logger.error("binwalk scan timed out")
    except Exception as e:
        logger.error(f"binwalk scan error: {e}")
    return results


def _run_binwalk_extract(file_path: str, extract_dir: str) -> Tuple[bool, Optional[str]]:
    """Run binwalk extraction. Returns (success, error_message)."""
    try:
        proc = subprocess.run(
            ["binwalk", "--extract", "--directory", extract_dir, file_path],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if proc.returncode not in (0, 1):
            return False, proc.stderr[:500] if proc.stderr else "Extraction failed"
        return True, None
    except FileNotFoundError:
        logger.warning("binwalk not found — creating mock extraction for development")
        _create_mock_extraction(extract_dir)
        return True, None
    except subprocess.TimeoutExpired:
        return False, "Extraction timed out after 600 seconds"
    except Exception as e:
        return False, str(e)


def _mock_scan_results(file_path: str) -> List[Dict[str, Any]]:
    """Return realistic mock binwalk output for development without binwalk installed."""
    size = os.path.getsize(file_path)
    return [
        {"offset": 0, "hex_offset": "0x0", "description": "ELF, 32-bit LSB executable, ARM, version 1 (SYSV)"},
        {"offset": 512, "hex_offset": "0x200", "description": "LZMA compressed data, properties: 0x5D, dictionary size: 8388608 bytes"},
        {"offset": 1048576, "hex_offset": "0x100000", "description": "Squashfs filesystem, little endian, version 4.0"},
        {"offset": size // 2, "hex_offset": hex(size // 2), "description": "gzip compressed data, from Unix"},
    ]


def _create_mock_extraction(extract_dir: str):
    """Create a realistic mock extraction directory structure."""
    os.makedirs(extract_dir, exist_ok=True)
    dirs = [
        "squashfs-root/etc",
        "squashfs-root/bin",
        "squashfs-root/lib",
        "squashfs-root/usr/bin",
        "squashfs-root/var/log",
    ]
    for d in dirs:
        os.makedirs(os.path.join(extract_dir, d), exist_ok=True)

    mock_files = {
        "squashfs-root/etc/passwd": "root:x:0:0:root:/root:/bin/sh\ndaemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin\n",
        "squashfs-root/etc/shadow": "root:$1$xyz$mockhashvalue:18000:0:99999:7:::\n",
        "squashfs-root/etc/hostname": "firmware-device\n",
        "squashfs-root/etc/version": "1.0.0-release\n",
        "squashfs-root/bin/busybox": b"\x7fELF\x01\x01\x01" + b"\x00" * 100,
        "squashfs-root/var/log/syslog": "Jan  1 00:00:00 kernel: Linux version 4.14\n",
    }
    for rel_path, content in mock_files.items():
        full_path = os.path.join(extract_dir, rel_path)
        mode = "w" if isinstance(content, str) else "wb"
        with open(full_path, mode) as f:
            f.write(content)


def _build_file_tree(base_dir: str, max_depth: int = 6) -> Dict[str, Any]:
    """Recursively build a file tree from extracted directory."""
    def _recurse(path: str, depth: int) -> Dict[str, Any]:
        name = os.path.basename(path) or path
        node: Dict[str, Any] = {"name": name, "path": path.replace(base_dir, ""), "type": "directory", "children": []}
        if depth >= max_depth:
            return node
        try:
            entries = sorted(os.scandir(path), key=lambda e: (e.is_file(), e.name))
            for entry in entries[:200]:  # cap to prevent huge trees
                if entry.is_dir(follow_symlinks=False):
                    node["children"].append(_recurse(entry.path, depth + 1))
                else:
                    node["children"].append({
                        "name": entry.name,
                        "path": entry.path.replace(base_dir, ""),
                        "type": "file",
                        "size": entry.stat().st_size,
                    })
        except PermissionError:
            pass
        return node

    if not os.path.isdir(base_dir):
        return {"name": "empty", "path": "/", "type": "directory", "children": []}
    return _recurse(base_dir, 0)


def _count_files_and_size(directory: str) -> Tuple[int, int]:
    count = 0
    total = 0
    for root, _, files in os.walk(directory):
        for f in files:
            count += 1
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return count, total


def _build_component_summary(scan_results: List[Dict]) -> Dict[str, Any]:
    """Derive high-level component detection from scan signatures."""
    tags = {
        "filesystems": [],
        "compression": [],
        "executables": [],
        "certificates": [],
        "archives": [],
        "kernels": [],
        "bootloaders": [],
    }
    desc_lower_list = [r["description"].lower() for r in scan_results]
    fs_keywords = {"squashfs": "SquashFS", "cramfs": "CramFS", "jffs2": "JFFS2", "ext2": "ext2/3/4", "fat": "FAT", "yaffs": "YAFFS"}
    comp_keywords = {"lzma": "LZMA", "gzip": "gzip", "zlib": "zlib", "bzip2": "bzip2", "xz": "XZ"}
    exec_keywords = {"elf": "ELF Binary", "pe32": "PE Executable"}
    kernel_keywords = {"linux kernel": "Linux Kernel", "uimage": "U-Boot uImage"}
    boot_keywords = {"u-boot": "U-Boot", "grub": "GRUB"}
    cert_keywords = {"certificate": "X.509 Certificate", "private key": "Private Key"}

    for desc in desc_lower_list:
        for kw, label in fs_keywords.items():
            if kw in desc and label not in tags["filesystems"]:
                tags["filesystems"].append(label)
        for kw, label in comp_keywords.items():
            if kw in desc and label not in tags["compression"]:
                tags["compression"].append(label)
        for kw, label in exec_keywords.items():
            if kw in desc and label not in tags["executables"]:
                tags["executables"].append(label)
        for kw, label in kernel_keywords.items():
            if kw in desc and label not in tags["kernels"]:
                tags["kernels"].append(label)
        for kw, label in boot_keywords.items():
            if kw in desc and label not in tags["bootloaders"]:
                tags["bootloaders"].append(label)
        for kw, label in cert_keywords.items():
            if kw in desc and label not in tags["certificates"]:
                tags["certificates"].append(label)

    tags["total_signatures"] = len(scan_results)
    return tags


async def run_extraction(
    firmware_id: str,
    file_path: str,
    extract_base_dir: str,
) -> Dict[str, Any]:
    """
    Full async extraction pipeline.
    Returns a dict matching ExtractionResult fields.
    """
    started_at = datetime.now(timezone.utc)
    t0 = time.time()

    extract_dir = os.path.join(extract_base_dir, firmware_id)
    os.makedirs(extract_dir, exist_ok=True)

    # Step 1: Binwalk scan (run in thread pool)
    loop = asyncio.get_event_loop()
    scan_results = await loop.run_in_executor(None, _run_binwalk_scan, file_path)

    # Step 2: Binwalk extract
    success, error_msg = await loop.run_in_executor(
        None, _run_binwalk_extract, file_path, extract_dir
    )

    completed_at = datetime.now(timezone.utc)
    duration = time.time() - t0

    if not success:
        return {
            "status": "failed",
            "error_message": error_msg,
            "scan_results": scan_results,
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_seconds": duration,
        }

    # Step 3: Build file tree
    file_tree = await loop.run_in_executor(None, _build_file_tree, extract_dir)
    total_files, total_size = await loop.run_in_executor(None, _count_files_and_size, extract_dir)
    component_summary = _build_component_summary(scan_results)

    return {
        "status": "completed",
        "extraction_path": extract_dir,
        "scan_results": scan_results,
        "file_tree": file_tree,
        "component_summary": component_summary,
        "total_files_extracted": total_files,
        "total_size_extracted": total_size,
        "duration_seconds": round(duration, 2),
        "started_at": started_at,
        "completed_at": completed_at,
    }