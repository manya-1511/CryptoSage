"""
analysis/disassembler.py

Static disassembly for the Firmware Analysis Engine, using Capstone.

Disassembles a binary's executable section(s) and produces instruction
statistics: total instruction count, an opcode (mnemonic) histogram,
and counts of jump/call/return/arithmetic/logical/memory/branch
instructions. This module deliberately does **not** reconstruct a
control-flow graph -- only linear disassembly and instruction-level
statistics, per the Phase 4 scope.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

try:
    import capstone
except ImportError:  # pragma: no cover - dependency is required at runtime
    capstone = None

logger = logging.getLogger("cryptosage.analysis.disassembler")

# Capstone architecture/mode lookup keyed by (canonical architecture
# name, pointer size in bits). Extending to a new architecture is a
# config change here, not a rewrite of the disassembly logic below.
_CAPSTONE_ARCH_MAP: dict[tuple[str, int], tuple[int, int]] = {}
if capstone is not None:
    _CAPSTONE_ARCH_MAP = {
        ("x86_64", 64): (capstone.CS_ARCH_X86, capstone.CS_MODE_64),
        ("x86_64", 32): (capstone.CS_ARCH_X86, capstone.CS_MODE_32),
        ("x86", 32): (capstone.CS_ARCH_X86, capstone.CS_MODE_32),
        ("arm", 32): (capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM),
        ("arm64", 64): (capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM),
        ("mips", 32): (capstone.CS_ARCH_MIPS, capstone.CS_MODE_MIPS32),
    }

# Mnemonic-prefix -> instruction category, used to build the per-category
# counts requested alongside the raw opcode histogram. Checked against
# the start of each disassembled mnemonic (x86-oriented; extending to
# another architecture only requires adding another prefix set).
_JUMP_PREFIXES = (
    "jmp", "je", "jne", "jz", "jnz", "jg", "jge", "jl", "jle",
    "ja", "jae", "jb", "jbe", "js", "jns", "jo", "jno", "jp", "jnp",
    "jcxz", "jecxz", "jrcxz",
)
_CALL_PREFIXES = ("call",)
_RETURN_PREFIXES = ("ret", "retn", "retf", "iret", "iretd", "iretq")
_ARITHMETIC_PREFIXES = (
    "add", "sub", "mul", "imul", "div", "idiv", "inc", "dec",
    "neg", "adc", "sbb",
)
_LOGICAL_PREFIXES = ("and", "or", "xor", "not", "shl", "shr", "sar", "sal", "rol", "ror")
_MEMORY_PREFIXES = ("mov", "lea", "push", "pop", "movzx", "movsx", "movsxd")


def _categorize_instruction(mnemonic: str) -> Optional[str]:
    """Classify a single disassembled mnemonic into a broad instruction category."""
    lowered = mnemonic.lower()
    if lowered.startswith(_CALL_PREFIXES):
        return "call"
    if lowered.startswith(_RETURN_PREFIXES):
        return "return"
    if lowered.startswith(_JUMP_PREFIXES):
        return "jump"
    if lowered.startswith(_ARITHMETIC_PREFIXES):
        return "arithmetic"
    if lowered.startswith(_LOGICAL_PREFIXES):
        return "logical"
    if lowered.startswith(_MEMORY_PREFIXES):
        return "memory"
    return None


def disassemble_section(
    section_bytes: bytes,
    base_address: int,
    architecture: Optional[str],
    bitness: int = 64,
) -> Optional[dict[str, Any]]:
    """Disassemble a single section's raw bytes and return instruction statistics.

    Never raises: an unsupported architecture, missing Capstone, or a
    disassembly error results in `None` (logged), not an exception.

    Returns a dict with keys: `instruction_count`, `opcode_histogram`,
    `jump_count`, `call_count`, `return_count`, `arithmetic_count`,
    `logical_count`, `memory_count`, `branch_count` (jump + call
    combined), and `instruction_frequency` (opcode histogram normalized
    to fractions of `instruction_count`).
    """
    if capstone is None:
        logger.error("Capstone is not installed; cannot disassemble.")
        return None
    if not section_bytes or architecture is None:
        return None

    cs_arch_mode = _CAPSTONE_ARCH_MAP.get((architecture, bitness))
    if cs_arch_mode is None:
        logger.warning(
            "No Capstone mapping for architecture=%s bitness=%s; skipping disassembly.",
            architecture, bitness,
        )
        return None

    try:
        engine = capstone.Cs(*cs_arch_mode)
        engine.detail = False

        instruction_count = 0
        opcode_histogram: dict[str, int] = {}
        mnemonic_sequence: list[str] = []
        category_counts = {
            "jump": 0, "call": 0, "return": 0, "arithmetic": 0,
            "logical": 0, "memory": 0,
        }

        for insn in engine.disasm(section_bytes, base_address):
            instruction_count += 1
            mnemonic = insn.mnemonic
            opcode_histogram[mnemonic] = opcode_histogram.get(mnemonic, 0) + 1
            mnemonic_sequence.append(mnemonic)
            category = _categorize_instruction(mnemonic)
            if category is not None:
                category_counts[category] += 1

        instruction_frequency = (
            {mnemonic: round(count / instruction_count, 6) for mnemonic, count in opcode_histogram.items()}
            if instruction_count
            else {}
        )

        return {
            "instruction_count": instruction_count,
            "opcode_histogram": opcode_histogram,
            "mnemonic_sequence": mnemonic_sequence,
            "jump_count": category_counts["jump"],
            "call_count": category_counts["call"],
            "return_count": category_counts["return"],
            "arithmetic_count": category_counts["arithmetic"],
            "logical_count": category_counts["logical"],
            "memory_count": category_counts["memory"],
            "branch_count": category_counts["jump"] + category_counts["call"],
            "instruction_frequency": instruction_frequency,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("Disassembly failed for architecture=%s: %s", architecture, exc)
        return None


def disassemble_binary(binary: "lief.Binary", architecture: Optional[str], bitness: int = 64) -> Optional[dict[str, Any]]:  # noqa: F821
    """Disassemble a parsed LIEF binary's `.text` section.

    Convenience wrapper around `disassemble_section` for the common case
    of analyzing a binary's primary executable section.
    """
    try:
        text_section = binary.get_section(".text")
        if text_section is None:
            return None
        section_bytes = bytes(text_section.content)
        base_address = int(text_section.virtual_address)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not read .text section: %s", exc)
        return None

    return disassemble_section(section_bytes, base_address, architecture, bitness)
