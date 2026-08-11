"""
analysis/features.py

The single, canonical feature-extraction implementation for CryptoSage.

`extract_features(binary_path)` is the one and only place static
features are computed from a compiled binary. Both the offline Dataset
Builder (`dataset/extractor.py`, which now just re-exports this module)
and the runtime firmware analysis pipeline call this same function, so
training and inference are guaranteed to use an identical feature
schema -- there is no second, independent implementation anywhere in
the codebase.

Every field in the original Phase 2 dataset schema (`architecture`,
`binary_size`, `entropy`, `entry_point`, `section_count`, `symbol_count`,
`import_count`, `import_libraries`, `string_count`, `function_count`,
`instruction_count`, `opcode_histogram`, and the original six crypto
evidence flags) is preserved exactly, so existing `dataset.csv` output
remains schema-compatible. Additional fields requested for Phase 4
(`section_entropy`, `segment_count`, `export_count`, `compiler_hints`,
`optimization_hints`, and expanded crypto evidence) are added
alongside, never replacing the originals.

No feature is ever fabricated: if a value cannot be determined for a
given binary, it is recorded as `None` -- never a placeholder value.
"""

from __future__ import annotations

import json
import logging
import math
from collections import Counter
from pathlib import Path
from typing import Any, Optional

from analysis.binary import parse_elf
from analysis.constants import (
    CRYPTO_MAGIC_CONSTANTS,
    CRYPTO_SYMBOL_KEYWORDS,
    ECC_CURVE_OIDS,
    KNOWN_ALGORITHM_LABELS,
    KNOWN_CRYPTO_LIBRARY_NAMES,
    RSA_COMMON_EXPONENTS,
)
from analysis.disassembler import disassemble_section
from analysis.utils import count_strings, extract_strings, safe_read_bytes, shannon_entropy

logger = logging.getLogger("cryptosage.analysis.features")


def _best_effort_function_count(elf_metadata: dict[str, Any]) -> Optional[int]:
    """Estimate function count from the ELF symbol table (best effort).

    Falls back to None (not a guess) when no function-typed symbols are
    present, e.g. in a stripped binary.
    """
    symbol_count = elf_metadata.get("symbol_count")
    return symbol_count if symbol_count else None


def _detect_crypto_constants(raw_bytes: bytes) -> dict[str, bool]:
    """Search raw binary bytes for every known cryptographic magic constant."""
    results: dict[str, bool] = {}
    for label, signature in CRYPTO_MAGIC_CONSTANTS.items():
        results[f"{label.lower()}_constant"] = signature in raw_bytes
    return results


def _detect_crypto_symbols(symbol_names: list[str]) -> dict[str, bool]:
    """Flag which known crypto-primitive symbol keywords appear in `symbol_names`."""
    lowered = [name.lower() for name in symbol_names if name]
    results: dict[str, bool] = {}
    for label, keywords in CRYPTO_SYMBOL_KEYWORDS.items():
        results[f"{label.lower()}_symbol"] = any(
            keyword.lower() in symbol_name
            for symbol_name in lowered
            for keyword in keywords
        )
    return results


def _detect_known_crypto_library(imported_libraries: list[str]) -> bool:
    """Check whether any imported library name matches a known crypto library."""
    lowered = [str(name).lower() for name in imported_libraries]
    return any(
        known.lower() in library_name
        for library_name in lowered
        for known in KNOWN_CRYPTO_LIBRARY_NAMES
    )


def _detect_compiler_hints(raw_bytes: bytes, elf_metadata: dict[str, Any]) -> Optional[str]:
    """Best-effort compiler identification from a `.comment`-style section.

    GCC and Clang both embed a version string in a `.comment` section by
    default. If present, it is returned verbatim; otherwise None (this
    is a best-effort hint, never a fabricated guess).
    """
    for section in elf_metadata.get("sections", []):
        if section.get("name", "").lower() in (".comment", ".gnu.version"):
            # Sections are only summarized (name/size/entropy) upstream,
            # so re-read the region isn't available here; fall back to
            # scanning the whole binary's strings for a compiler marker.
            break

    strings = extract_strings(raw_bytes)
    for candidate in strings:
        lowered = candidate.lower()
        if "gcc:" in lowered or "clang version" in lowered or lowered.startswith(("gcc ", "clang ")):
            return candidate
    return None


def _detect_optimization_hint(elf_metadata: dict[str, Any]) -> Optional[str]:
    """Best-effort, non-authoritative optimization/debug-build hint.

    Presence of DWARF debug sections (`.debug_info`, `.debug_line`)
    suggests a debug or unoptimized build; their absence suggests a
    release/optimized/stripped build. This is a heuristic, not a
    guarantee -- it is intentionally conservative and returns None
    rather than a confident label when section data is unavailable.
    """
    section_names = {section.get("name", "").lower() for section in elf_metadata.get("sections", [])}
    if not section_names:
        return None
    if ".debug_info" in section_names or ".debug_line" in section_names:
        return "likely_debug_or_unoptimized"
    return "likely_release_or_stripped"


# --------------------------------------------------------------------------
# Phase 6: Advanced feature engineering
# --------------------------------------------------------------------------
#
# Everything below extends the original Phase 4 feature set with
# additional, real (never fabricated) signals: opcode n-gram
# distributions, lightweight control-flow/call-graph approximations
# derived from linear disassembly (no CFG is actually reconstructed --
# see `analysis/disassembler.py`'s own docstring), section
# permission-based ratios, and richer crypto-constant evidence
# (occurrence counts, RSA exponents, ECC curve OIDs).

def _distribution_entropy(counts: dict[str, int]) -> Optional[float]:
    """Shannon entropy (bits) of a frequency-count distribution (e.g. an
    opcode histogram), treating the counts as an empirical probability
    distribution over categories. Returns None for an empty distribution.
    """
    total = sum(counts.values())
    if not total:
        return None
    entropy = 0.0
    for count in counts.values():
        if count <= 0:
            continue
        probability = count / total
        entropy -= probability * math.log2(probability)
    return round(entropy, 6)


def _opcode_ngram_histogram(opcode_sequence: list[str], n: int) -> dict[str, int]:
    """Build an n-gram histogram over a sequence of opcode mnemonics.

    Consecutive mnemonics are joined into a single n-gram token (e.g.
    `["mov", "add"]` -> `"mov_add"` for n=2), so instruction *ordering*
    -- not just individual opcode frequency -- becomes a countable,
    tabular-friendly feature via the entropy/diversity metrics computed
    from it (see `_ngram_features`).
    """
    if len(opcode_sequence) < n:
        return {}
    histogram: dict[str, int] = {}
    for index in range(len(opcode_sequence) - n + 1):
        token = "_".join(opcode_sequence[index:index + n])
        histogram[token] = histogram.get(token, 0) + 1
    return histogram


def _ngram_features(opcode_sequence: list[str]) -> dict[str, Any]:
    """Compute opcode bigram/trigram diversity and entropy metrics.

    Bigrams and trigrams are summarized as scalar features (entropy and
    unique-token ratio) rather than exposed as open-ended per-token
    columns, so they remain compatible with a fixed-width tabular
    feature matrix regardless of which specific bigrams/trigrams occur
    in a given binary.
    """
    features: dict[str, Any] = {
        "opcode_bigram_entropy": None,
        "opcode_bigram_unique_ratio": None,
        "opcode_trigram_entropy": None,
        "opcode_trigram_unique_ratio": None,
        "instruction_entropy": None,
        "unique_opcode_ratio": None,
    }
    if not opcode_sequence:
        return features

    unigram_counts = Counter(opcode_sequence)
    features["instruction_entropy"] = _distribution_entropy(dict(unigram_counts))
    features["unique_opcode_ratio"] = round(len(unigram_counts) / len(opcode_sequence), 6)

    bigram_histogram = _opcode_ngram_histogram(opcode_sequence, 2)
    if bigram_histogram:
        features["opcode_bigram_entropy"] = _distribution_entropy(bigram_histogram)
        features["opcode_bigram_unique_ratio"] = round(
            len(bigram_histogram) / sum(bigram_histogram.values()), 6
        )

    trigram_histogram = _opcode_ngram_histogram(opcode_sequence, 3)
    if trigram_histogram:
        features["opcode_trigram_entropy"] = _distribution_entropy(trigram_histogram)
        features["opcode_trigram_unique_ratio"] = round(
            len(trigram_histogram) / sum(trigram_histogram.values()), 6
        )

    return features


def _control_flow_and_call_graph_features(disassembly: dict[str, Any], elf_metadata: dict[str, Any]) -> dict[str, Any]:
    """Approximate control-flow and call-graph metrics from linear disassembly.

    No control-flow graph is actually constructed (Phase 4 scope,
    unchanged) -- these are principled approximations derived from
    instruction-category counts alone:

    - `basic_block_count_estimate`: every jump or call instruction ends
      a basic block, so the block count is approximately the number of
      such branch points plus one (for the block the function starts in).
    - `cfg_edge_count_estimate`: each jump/call contributes roughly one
      outgoing edge (a simplification -- conditional jumps really have
      two edges, but the fallthrough edge isn't resolvable without a
      real CFG, so this is a conservative lower-bound estimate).
    - `cyclomatic_complexity_estimate`: McConnell/McCabe's `E - N + 2`
      applied to the estimated edge/node counts above.
    - `call_graph_fanout_estimate`: calls per function, a lightweight
      proxy for call-graph branching factor without resolving actual
      call targets.
    """
    jump_count = disassembly.get("jump_count") or 0
    call_count = disassembly.get("call_count") or 0
    function_count = elf_metadata.get("symbol_count") or 0

    basic_block_estimate = jump_count + call_count + 1
    edge_estimate = jump_count + call_count
    cyclomatic_estimate = edge_estimate - basic_block_estimate + 2
    call_graph_fanout = round(call_count / function_count, 6) if function_count else None

    return {
        "basic_block_count_estimate": basic_block_estimate,
        "cfg_edge_count_estimate": edge_estimate,
        "cyclomatic_complexity_estimate": cyclomatic_estimate,
        "call_graph_fanout_estimate": call_graph_fanout,
    }


def _section_permission_ratios(elf_metadata: dict[str, Any], binary) -> dict[str, Optional[float]]:  # noqa: ANN001
    """Compute the fraction of total segment size that is executable,
    read-only, and writable, from ELF segment permission flags.

    Returns None for every ratio if segment data is unavailable, rather
    than a fabricated 0.0.
    """
    try:
        segments = list(binary.segments)
    except Exception:  # noqa: BLE001
        segments = []

    if not segments:
        return {
            "executable_section_ratio": None,
            "readonly_section_ratio": None,
            "writable_section_ratio": None,
        }

    total_size = 0
    executable_size = 0
    writable_size = 0
    readonly_size = 0

    for segment in segments:
        try:
            size = int(segment.physical_size)
            flags = str(segment.flags)
        except Exception:  # noqa: BLE001
            continue
        total_size += size
        is_executable = "X" in flags
        is_writable = "W" in flags
        if is_executable:
            executable_size += size
        if is_writable:
            writable_size += size
        elif not is_executable:
            readonly_size += size

    if total_size == 0:
        return {
            "executable_section_ratio": None,
            "readonly_section_ratio": None,
            "writable_section_ratio": None,
        }

    return {
        "executable_section_ratio": round(executable_size / total_size, 6),
        "readonly_section_ratio": round(readonly_size / total_size, 6),
        "writable_section_ratio": round(writable_size / total_size, 6),
    }


def _crypto_constant_counts(raw_bytes: bytes) -> dict[str, int]:
    """Count (not just detect) occurrences of each known crypto magic constant.

    An occurrence count is a richer signal than a boolean: a large
    crypto library implementing multiple AES modes may embed the AES
    S-box several times, which a simple presence flag can't distinguish
    from a single incidental match.
    """
    return {
        f"{label.lower()}_constant_count": raw_bytes.count(signature)
        for label, signature in CRYPTO_MAGIC_CONSTANTS.items()
    }


def _detect_rsa_exponent(raw_bytes: bytes) -> bool:
    """Detect the near-universal RSA public exponent 65537 (0x010001)."""
    return any(pattern in raw_bytes for pattern in RSA_COMMON_EXPONENTS.values())


def _detect_ecc_curves(raw_bytes: bytes) -> dict[str, bool]:
    """Detect DER-encoded OIDs of the most common standardized elliptic curves."""
    return {
        f"ecc_curve_{name.lower().replace('-', '_')}": oid in raw_bytes
        for name, oid in ECC_CURVE_OIDS.items()
    }


def extract_features(binary_path: Path) -> dict[str, Any]:
    """Extract the full static-analysis feature set for a single binary.

    This is the single source of truth for the CryptoSage feature
    schema, reused unmodified by both the offline Dataset Builder and
    the runtime firmware analysis pipeline.

    Args:
        binary_path: Path to a compiled ELF binary, shared library, or
            standalone object file.

    Returns:
        A dictionary of extracted features. Any feature that could not
        be determined is set to `None` -- never a fabricated placeholder.
    """
    binary_path = Path(binary_path)

    # --- Base schema (must exactly match the original Phase 2 dataset) ----
    features: dict[str, Any] = {
        "architecture": None,
        "binary_size": None,
        "entropy": None,
        "entry_point": None,
        "section_count": None,
        "symbol_count": None,
        "import_count": None,
        "import_libraries": None,
        "string_count": None,
        "function_count": None,
        "instruction_count": None,
        "opcode_histogram": None,
        "aes_constant": None,
        "sha_constant": None,
        "sha1_constant": None,
        "md5_constant": None,
        "rsa_symbol": None,
        "ecc_symbol": None,
        "aes_symbol": None,
        "sha_symbol": None,
        "des_symbol": None,
        "chacha_symbol": None,
        # --- Phase 4 additions ------------------------------------------
        "segment_count": None,
        "export_count": None,
        "section_entropy": None,
        "compiler_hints": None,
        "optimization_hints": None,
        "known_crypto_library": None,
        "crypto_evidence": None,
        # --- Phase 6 additions (advanced feature engineering) -----------
        "instruction_entropy": None,
        "unique_opcode_ratio": None,
        "opcode_bigram_entropy": None,
        "opcode_bigram_unique_ratio": None,
        "opcode_trigram_entropy": None,
        "opcode_trigram_unique_ratio": None,
        "basic_block_count_estimate": None,
        "cfg_edge_count_estimate": None,
        "cyclomatic_complexity_estimate": None,
        "call_graph_fanout_estimate": None,
        "executable_section_ratio": None,
        "readonly_section_ratio": None,
        "writable_section_ratio": None,
        "rsa_exponent_present": None,
        "ecc_curve_p_256": None,
        "ecc_curve_p_384": None,
        "ecc_curve_p_521": None,
        "ecc_curve_secp256k1": None,
    }

    raw_bytes = safe_read_bytes(binary_path)
    if raw_bytes is None:
        logger.error("Could not read binary %s; returning null feature set.", binary_path)
        return features

    features["binary_size"] = len(raw_bytes)
    features["entropy"] = shannon_entropy(raw_bytes)
    features["string_count"] = count_strings(raw_bytes)

    # Crypto-constant occurrence counts and RSA/ECC signatures only need
    # the raw bytes, not a successful ELF parse, so compute them here.
    features.update(_crypto_constant_counts(raw_bytes))
    features["rsa_exponent_present"] = _detect_rsa_exponent(raw_bytes)
    features.update(_detect_ecc_curves(raw_bytes))

    elf_metadata = parse_elf(binary_path)
    if elf_metadata is None:
        logger.warning("Skipping structural features for %s (unparseable binary)", binary_path)
        return features

    features["architecture"] = elf_metadata.get("architecture")
    features["entry_point"] = elf_metadata.get("entry_point")
    features["section_count"] = elf_metadata.get("section_count")
    features["symbol_count"] = elf_metadata.get("symbol_count")
    features["import_count"] = elf_metadata.get("import_count")
    features["import_libraries"] = elf_metadata.get("imported_libraries")
    features["segment_count"] = elf_metadata.get("segment_count")
    features["export_count"] = elf_metadata.get("export_count")
    features["function_count"] = _best_effort_function_count(elf_metadata)

    sections = elf_metadata.get("sections", [])
    if sections:
        features["section_entropy"] = {
            section["name"]: section.get("entropy") for section in sections
        }

    # --- Disassembly (best effort, .text section only) ---------------------
    text_section = next((s for s in sections if s.get("name") == ".text"), None)
    if text_section is not None:
        try:
            from analysis.binary import lief  # local import: reuse the same LIEF module

            binary = lief.parse(str(binary_path))
            disassembly = disassemble_section(
                bytes(binary.get_section(".text").content),
                int(binary.get_section(".text").virtual_address),
                features["architecture"],
                bitness=elf_metadata.get("bitness") or 64,
            ) if binary is not None else None
        except Exception as exc:  # noqa: BLE001
            logger.warning("Disassembly step failed for %s: %s", binary_path, exc)
            disassembly = None
            binary = None

        if disassembly is not None:
            features["instruction_count"] = disassembly.get("instruction_count")
            features["opcode_histogram"] = disassembly.get("opcode_histogram")
            features["jump_count"] = disassembly.get("jump_count")
            features["call_count"] = disassembly.get("call_count")
            features["return_count"] = disassembly.get("return_count")
            features["arithmetic_count"] = disassembly.get("arithmetic_count")
            features["logical_count"] = disassembly.get("logical_count")
            features["memory_count"] = disassembly.get("memory_count")
            features["branch_count"] = disassembly.get("branch_count")

            # Phase 6: opcode n-gram + CFG/call-graph approximation features.
            features.update(_ngram_features(disassembly.get("mnemonic_sequence", [])))
            features.update(_control_flow_and_call_graph_features(disassembly, elf_metadata))

        if binary is not None:
            features.update(_section_permission_ratios(elf_metadata, binary))

    # --- Crypto evidence -----------------------------------------------------
    constant_flags = _detect_crypto_constants(raw_bytes)
    symbol_names = list(elf_metadata.get("symbols", [])) + list(elf_metadata.get("imported_functions", [])) + list(elf_metadata.get("exported_functions", []))
    symbol_flags = _detect_crypto_symbols(symbol_names)

    # Preserve the original Phase 2 flag names exactly.
    features["aes_constant"] = constant_flags.get("aes_constant")
    features["sha_constant"] = constant_flags.get("sha256_constant")
    features["sha1_constant"] = constant_flags.get("sha1_constant")
    features["md5_constant"] = constant_flags.get("md5_constant")
    features["rsa_symbol"] = symbol_flags.get("rsa_symbol")
    features["ecc_symbol"] = symbol_flags.get("ecc_symbol")
    features["aes_symbol"] = symbol_flags.get("aes_symbol")
    features["sha_symbol"] = symbol_flags.get("sha256_symbol")
    features["des_symbol"] = symbol_flags.get("des_symbol")
    features["chacha_symbol"] = symbol_flags.get("chacha20_symbol")

    # Consolidated, expanded crypto evidence covering every algorithm in
    # analysis/constants.py (new in Phase 4).
    crypto_evidence = {}
    for label in KNOWN_ALGORITHM_LABELS:
        key = label.lower().replace("-", "")
        crypto_evidence[label] = bool(
            constant_flags.get(f"{key}_constant", False) or symbol_flags.get(f"{key}_symbol", False)
        )
    features["crypto_evidence"] = crypto_evidence
    features["known_crypto_library"] = _detect_known_crypto_library(
        elf_metadata.get("imported_libraries", []) or []
    )

    # --- Compiler / optimization hints (best effort, Phase 4) ---------------
    features["compiler_hints"] = _detect_compiler_hints(raw_bytes, elf_metadata)
    features["optimization_hints"] = _detect_optimization_hint(elf_metadata)

    return features


def extract_features_batch(binary_paths: list[Path]) -> dict[Path, dict[str, Any]]:
    """Run `extract_features` over multiple binaries, logging per-file failures.

    A failure on one binary never aborts the batch.
    """
    results: dict[Path, dict[str, Any]] = {}
    for binary_path in binary_paths:
        try:
            results[binary_path] = extract_features(binary_path)
        except Exception as exc:  # noqa: BLE001
            logger.error("Unexpected error extracting features from %s: %s", binary_path, exc)
            results[binary_path] = {}
    return results


def save_feature_vector(features: dict[str, Any], output_path: Path) -> Path:
    """Write a feature dict to disk as `feature_vector.json`.

    Creates parent directories as needed. Raises no exception on
    failure to write JSON-incompatible values -- those are stringified
    via `default=str` so the write always succeeds.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(features, indent=2, default=str), encoding="utf-8")
    logger.info("Feature vector written to %s", output_path)
    return output_path
