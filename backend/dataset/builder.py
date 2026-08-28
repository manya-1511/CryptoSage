 

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

import config
from extractor import extract_features

logger = logging.getLogger("cryptosage.dataset.builder")

# Feature keys from analysis.features.extract_features() that are NOT
# flat scalars (dicts, lists) and therefore can't go directly into a
# tabular CSV column -- handled separately (or intentionally omitted)
# rather than being auto-flattened.
_NON_SCALAR_FEATURE_KEYS: frozenset[str] = frozenset({
    "opcode_histogram", "section_entropy", "crypto_evidence",
    "import_libraries", "mnemonic_sequence", "instruction_frequency",
})


def _flatten_scalar_features(features: dict) -> dict:
    """Return every scalar-valued (int/float/bool/str/None) feature.

    Used so that new features added to `analysis/features.py` (Phase 6
    and beyond) automatically flow into the generated dataset without
    requiring `build_object_dataset_row`/`build_dataset_row` to be
    updated every time a new feature is added -- a single feature
    source (Phase 4's design principle) should not require duplicate
    bookkeeping here.
    """
    return {
        key: value
        for key, value in features.items()
        if key not in _NON_SCALAR_FEATURE_KEYS and not isinstance(value, (dict, list))
    }


def _stringify_import_libraries(import_libraries: Optional[list]) -> Optional[str]:
    """Convert the extractor's list of imported library names to a single,
    CSV/hash-safe, pipe-delimited string (never a Python list literal).
    """
    if not import_libraries:
        return None
    return "|".join(sorted({str(name) for name in import_libraries}))


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def _configure_logging() -> Path:
    """Configure logging to both stdout and a dedicated per-run log file.

    Returns the path to the log file created for this run.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = config.LOGS_DIR / f"dataset_build_{timestamp}.log"

    root_logger = logging.getLogger("cryptosage.dataset")
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)

    return log_path


# ---------------------------------------------------------------------------
# Data classes for run bookkeeping
# ---------------------------------------------------------------------------

@dataclass
class BuildResult:
    """Outcome of building a single project at a single optimization level."""

    project: str
    optimization_level: str
    success: bool
    binaries_found: int = 0
    error: Optional[str] = None


@dataclass
class PipelineSummary:
    """Aggregate results across the whole pipeline run, for the final report."""

    successful_projects: set[str] = field(default_factory=set)
    failed_projects: dict[str, str] = field(default_factory=dict)
    total_binaries_processed: int = 0
    total_dataset_rows: int = 0
    build_results: list[BuildResult] = field(default_factory=list)
    objects_compiled: int = 0
    objects_failed: int = 0
    algorithms_detected: set[str] = field(default_factory=set)
    started_at: float = field(default_factory=time.monotonic)


# ---------------------------------------------------------------------------
# Step 1: Clone / update repositories
# ---------------------------------------------------------------------------

def clone_repository(project_name: str, project_cfg: dict) -> Optional[Path]:
    """Clone a project's repository if it is not already present.

    If the checkout already exists, it is updated (`git pull`) so the
    dataset can be regenerated against the latest upstream source on
    subsequent runs, without ever re-cloning from scratch.

    Returns the path to the source checkout, or None if cloning/updating
    failed.
    """
    source_dir = config.SOURCES_DIR / project_name / "src"

    if source_dir.exists() and any(source_dir.iterdir()):
        logger.info("[%s] Source already cloned at %s -- checking for updates.", project_name, source_dir)
        try:
            result = subprocess.run(
                ["git", "pull", "--ff-only"],
                cwd=source_dir,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode == 0:
                logger.info("[%s] Repository update check: %s", project_name, result.stdout.strip() or "up to date")
            else:
                logger.warning(
                    "[%s] Could not update repository (continuing with existing checkout): %s",
                    project_name, (result.stderr or "").strip()[:300],
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] Repository update check failed (continuing with existing checkout): %s", project_name, exc)
        return source_dir

    source_dir.parent.mkdir(parents=True, exist_ok=True)
    repo_url = project_cfg["repo_url"]
    logger.info("[%s] Cloning %s into %s ...", project_name, repo_url, source_dir)

    try:
        subprocess.run(
            [
                "git", "clone", "--depth", "1", "--recurse-submodules",
                repo_url, str(source_dir),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=config.BUILD_TIMEOUT_SECONDS,
        )
        logger.info("[%s] Clone completed successfully.", project_name)
        return source_dir
    except subprocess.CalledProcessError as exc:
        logger.error("[%s] Clone failed: %s", project_name, exc.stderr.strip() if exc.stderr else exc)
        return None
    except subprocess.TimeoutExpired:
        logger.error("[%s] Clone timed out after %s seconds.", project_name, config.BUILD_TIMEOUT_SECONDS)
        return None


# ---------------------------------------------------------------------------
# Step 2: Build system detection + full-library build
# ---------------------------------------------------------------------------

def detect_build_system(source_dir: Path, hint: str) -> str:
    """Auto-detect a project's build system, preferring the configured hint
    when it matches what is actually present in the checkout.
    """
    has_cmake = (source_dir / "CMakeLists.txt").exists()
    has_configure = (source_dir / "configure").exists() or (source_dir / "Configure").exists()
    has_autogen = (source_dir / "autogen.sh").exists()
    has_makefile = (source_dir / "Makefile").exists() or (source_dir / "makefile").exists()

    if hint == "cmake" and has_cmake:
        return "cmake"
    if hint == "autotools" and (has_configure or has_autogen):
        return "autotools"
    if hint == "make" and has_makefile:
        return "make"

    if has_cmake:
        return "cmake"
    if has_configure or has_autogen:
        return "autotools"
    if has_makefile:
        return "make"

    logger.warning("Could not detect a build system in %s; defaulting to 'make'.", source_dir)
    return "make"


def _clean_source_tree(source_dir: Path) -> None:
    """Reset a git checkout to a pristine state between optimization-level builds."""
    try:
        subprocess.run(
            ["git", "clean", "-fdx"],
            cwd=source_dir,
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
        subprocess.run(
            ["git", "checkout", "--", "."],
            cwd=source_dir,
            check=False,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not fully clean %s before rebuild: %s", source_dir, exc)


def _run_command(command: str, cwd: Path, env_extra: dict[str, str], timeout: Optional[int] = None) -> tuple[bool, str]:
    """Run a shell command (supports `&&` chains like wolfSSL's autogen+configure)."""
    import os

    env = os.environ.copy()
    env.update(env_extra)
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            shell=True,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout or config.BUILD_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            return False, (result.stderr or result.stdout or "unknown error")[-2000:]
        return True, ""
    except subprocess.TimeoutExpired:
        return False, f"Command timed out after {timeout or config.BUILD_TIMEOUT_SECONDS}s"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def build_project(
    project_name: str,
    project_cfg: dict,
    source_dir: Path,
    optimization_level: str,
    architecture: str = config.HOST_ARCHITECTURE,
) -> BuildResult:
    """Build a single project at a single optimization level (Phase 2A).

    Cleans the source tree first so each optimization level compiles the
    same pristine source, then invokes the appropriate build system with
    CFLAGS/CXXFLAGS set to the requested `-O<n>` level.
    """
    compiler = project_cfg.get("compiler", config.DEFAULT_COMPILER)
    toolchain = config.ARCHITECTURE_TOOLCHAINS.get(architecture, {"cc_prefix": "", "extra_cflags": ""})
    cc = f"{toolchain.get('cc_prefix') or ''}{compiler}"
    extra_cflags = toolchain.get("extra_cflags") or ""
    cflags = f"-{optimization_level} {extra_cflags}".strip()

    logger.info(
        "[%s] Building at %s (compiler=%s, arch=%s)...",
        project_name, optimization_level, cc, architecture,
    )

    _clean_source_tree(source_dir)

    build_system = detect_build_system(source_dir, project_cfg.get("build_system", "make"))
    env_extra = {"CC": cc, "CFLAGS": cflags, "CXXFLAGS": cflags}

    success = False
    error_message = ""

    if build_system == "autotools":
        configure_cmd = project_cfg.get("configure_cmd") or "./configure"
        configure_args = " ".join(project_cfg.get("configure_args", []))
        full_configure = f"{configure_cmd} {configure_args}".strip()
        success, error_message = _run_command(full_configure, source_dir, env_extra)
        if success:
            success, error_message = _run_command(
                f"make -j{config.MAKE_JOBS}", source_dir, env_extra
            )

    elif build_system == "cmake":
        build_dir = source_dir / f"build_{optimization_level}"
        build_dir.mkdir(exist_ok=True)
        cmake_args = " ".join(project_cfg.get("cmake_args", []))
        configure_cmd = (
            f"cmake -DCMAKE_C_FLAGS='{cflags}' -DCMAKE_CXX_FLAGS='{cflags}' "
            f"-DCMAKE_C_COMPILER={cc} {cmake_args} .."
        )
        success, error_message = _run_command(configure_cmd, build_dir, env_extra)
        if success:
            success, error_message = _run_command(
                f"make -j{config.MAKE_JOBS}", build_dir, env_extra
            )

    elif build_system == "make":
        make_file = project_cfg.get("make_file")
        file_arg = f"-f {make_file}" if make_file else ""
        success, error_message = _run_command(
            f"make {file_arg} -j{config.MAKE_JOBS} CC={cc} CFLAGS='{cflags}'", source_dir, env_extra
        )

    else:
        error_message = f"Unsupported build system '{build_system}'"

    if success:
        logger.info("[%s] Build succeeded at %s using %s.", project_name, optimization_level, build_system)
    else:
        logger.error("[%s] Build failed at %s: %s", project_name, optimization_level, error_message)

    return BuildResult(
        project=project_name,
        optimization_level=optimization_level,
        success=success,
        error=None if success else error_message,
    )


# ---------------------------------------------------------------------------
# Step 3 + 4: Discover and copy binaries (library-level)
# ---------------------------------------------------------------------------

def _is_ignored_path(path: Path) -> bool:
    """Return True if any path component matches an ignored-directory keyword."""
    lowered_parts = [part.lower() for part in path.parts]
    return any(
        keyword in part
        for part in lowered_parts
        for keyword in config.IGNORED_DIR_KEYWORDS
    )


def _is_elf_binary(path: Path) -> bool:
    """Check the ELF magic bytes to positively identify a compiled binary."""
    if path.suffix in config.IGNORED_EXTENSIONS:
        return False
    try:
        with path.open("rb") as handle:
            return handle.read(4) == config.ELF_MAGIC
    except OSError:
        return False


def discover_binaries(source_dir: Path) -> list[Path]:
    """Walk a build tree and return every valid ELF binary/library found."""
    discovered: list[Path] = []
    for path in source_dir.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        if _is_ignored_path(path.relative_to(source_dir)):
            continue
        if _is_elf_binary(path):
            discovered.append(path)
    logger.info("Discovered %d candidate binaries under %s", len(discovered), source_dir)
    return discovered


def _classify_binary_type(binary_path: Path) -> str:
    """Best-effort classification of a discovered binary's type."""
    name = binary_path.name
    if ".so" in name:
        return "shared_library"
    if binary_path.suffix == ".a":
        return "static_library"
    if binary_path.suffix == ".o":
        return "object"
    return "executable"


def copy_binaries_to_compiled(
    project_name: str,
    optimization_level: str,
    architecture: str,
    binaries: list[Path],
) -> list[Path]:
    """Copy discovered binaries into dataset/compiled/<project>/<opt>/<arch>/."""
    destination_dir = config.COMPILED_DIR / project_name / optimization_level / architecture
    destination_dir.mkdir(parents=True, exist_ok=True)

    copied: list[Path] = []
    seen_names: set[str] = set()
    for binary_path in binaries:
        name = binary_path.name
        if name in seen_names:
            name = f"{binary_path.parent.name}_{name}"
        seen_names.add(name)

        destination_path = destination_dir / name
        try:
            shutil.copy2(binary_path, destination_path)
            copied.append(destination_path)
        except OSError as exc:
            logger.warning("Could not copy %s -> %s: %s", binary_path, destination_path, exc)

    logger.info(
        "[%s] Copied %d binaries to %s", project_name, len(copied), destination_dir
    )
    return copied


# ---------------------------------------------------------------------------
# Step 7: Whole-binary label inference (Phase 2A)
# ---------------------------------------------------------------------------

def infer_label(binary_path: Path, project_name: str, features: dict) -> str:
    """Infer a crypto-algorithm label from filename, path, and symbol evidence.

    Used for whole-library/executable binaries (Phase 2A), where a
    single file may legitimately implement many algorithms at once.
    Priority order: filename keywords > containing-path keywords >
    detected crypto symbol/constant features. Falls back to NON_CRYPTO
    when nothing matches.
    """
    search_text = f"{binary_path.name} {binary_path.parent}".lower()
    for keyword, label in config.ALGORITHM_KEYWORDS.items():
        if keyword in search_text:
            return label

    if features.get("aes_constant") or features.get("aes_symbol"):
        return "AES"
    if features.get("sha_constant") or features.get("sha_symbol"):
        return "SHA256"
    if features.get("sha1_constant"):
        return "SHA1"
    if features.get("rsa_symbol"):
        return "RSA"
    if features.get("ecc_symbol"):
        return "ECC"
    if features.get("chacha_symbol"):
        return "ChaCha20"
    if features.get("des_symbol"):
        return "DES"

    return config.NON_CRYPTO_LABEL


# ---------------------------------------------------------------------------
# Phase 2B: Algorithm-level source discovery
# ---------------------------------------------------------------------------

_TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9]+")


def _match_algorithm_from_filename(path: Path) -> Optional[str]:
    """Identify which algorithm (if any) a single source file implements.

    Stricter than `infer_label`: this drives Phase 2B, where a confident
    per-file label is required (spec: "If an implementation cannot be
    identified confidently, skip it."). Uses exact filename-token
    matching first, then a length-gated substring fallback for
    distinctive compound filenames (e.g. "chacha20poly1305_encrypt.c").
    """
    stem = path.stem.lower()
    tokens = set(_TOKEN_SPLIT_RE.split(stem))
    tokens.add(stem)

    for keyword, label in config.ALGORITHM_SOURCE_KEYWORDS:
        if keyword in tokens:
            return label

    for keyword, label in config.ALGORITHM_SOURCE_KEYWORDS:
        if len(keyword) >= config.MIN_SUBSTRING_KEYWORD_LENGTH and keyword in stem:
            return label

    return None


def _is_non_implementation_file(path: Path) -> bool:
    """Return True if a filename marks a test/fuzz/demo/benchmark harness."""
    stem = path.stem.lower()
    return any(marker in stem for marker in config.NON_IMPLEMENTATION_FILENAME_MARKERS)


def discover_algorithm_source_files(source_dir: Path) -> dict[str, list[Path]]:
    """Walk a project's source tree and group `.c` files by detected algorithm.

    Only files matched confidently by `_match_algorithm_from_filename`
    are kept; everything else is skipped, per spec. Files under ignored
    directories (tests/docs/examples/etc.) or matching a test/fuzz/demo
    filename marker are excluded even if their name matches an algorithm
    keyword, since they are harnesses rather than implementations.
    """
    grouped: dict[str, list[Path]] = {}
    for path in source_dir.rglob("*.c"):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(source_dir)
        if _is_ignored_path(relative):
            continue
        if _is_non_implementation_file(path):
            continue

        algorithm = _match_algorithm_from_filename(path)
        if algorithm is None:
            continue

        grouped.setdefault(algorithm, []).append(path)

    total_files = sum(len(files) for files in grouped.values())
    logger.info(
        "Discovered %d candidate algorithm source file(s) across %d algorithm(s) under %s",
        total_files, len(grouped), source_dir,
    )
    return grouped


def discover_header_include_dirs(source_dir: Path, max_dirs: int = config.MAX_INCLUDE_DIRS) -> list[Path]:
    """Collect every directory under `source_dir` containing a header file.

    Used to build a generic `-I` include path list for compiling
    standalone object files without hardcoding per-project include
    directories -- keeping the pipeline config-driven rather than
    project-specific.

    Both a header's own directory and its *parent* directory are
    included. This matters for the common C convention of namespaced
    includes (e.g. `#include "internal/foo.h"` resolved from a
    `-Iinclude` flag when the real header lives at
    `include/internal/foo.h`) -- without the parent directory, only
    `#include "foo.h"` (flat) resolves, not the namespaced form used
    throughout OpenSSL and similar large codebases.
    """
    include_dirs: set[Path] = set()
    for header_path in source_dir.rglob("*.h"):
        relative = header_path.relative_to(source_dir)
        if _is_ignored_path(relative):
            continue
        include_dirs.add(header_path.parent)
        include_dirs.add(header_path.parent.parent)
        if len(include_dirs) >= max_dirs:
            break

    sorted_dirs = sorted(include_dirs, key=lambda p: len(p.parts))
    logger.info("Discovered %d header include director(y/ies) under %s", len(sorted_dirs), source_dir)
    return sorted_dirs


# ---------------------------------------------------------------------------
# Phase 2B: Standalone object-file compilation
# ---------------------------------------------------------------------------

def get_available_compilers() -> list[str]:
    """Return which of `config.OBJECT_PIPELINE_COMPILERS` are installed."""
    available = [name for name in config.OBJECT_PIPELINE_COMPILERS if shutil.which(name)]
    if not available:
        logger.error("No supported compiler (gcc/clang) found on this system.")
    return available


def _get_compiler_version(compiler: str) -> str:
    """Return the installed version string for a compiler, or 'unknown'."""
    try:
        result = subprocess.run(
            [compiler, "--version"], capture_output=True, text=True, timeout=10
        )
        first_line = (result.stdout or result.stderr or "").splitlines()
        return first_line[0].strip() if first_line else "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


def compile_object_file(
    source_file: Path,
    include_dirs: list[Path],
    compiler: str,
    optimization_level: str,
    build_type: str,
    output_path: Path,
) -> tuple[bool, str]:
    """Compile a single source file to a standalone object file (`-c`).

    Compiling one translation unit at a time (rather than an entire
    project) sidesteps most build-system/dependency complexity and is
    what makes it feasible to turn hundreds of individual algorithm
    implementations across five libraries into thousands of real,
    independent dataset samples.

    Returns (success, error_message).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    include_flags = " ".join(f"-I{d}" for d in include_dirs)
    build_flags = " ".join(config.BUILD_TYPES.get(build_type, []))

    command = (
        f"{compiler} -c -O{optimization_level.lstrip('O')} {build_flags} "
        f"{include_flags} '{source_file}' -o '{output_path}'"
    )

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0 and output_path.exists():
            return True, ""
        return False, (result.stderr or "unknown compile error")[-500:]
    except subprocess.TimeoutExpired:
        return False, "Compilation timed out after 60s"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def build_object_dataset_row(
    binary_path: Path,
    project_name: str,
    algorithm_label: str,
    architecture: str,
    optimization_level: str,
    compiler: str,
    compiler_version: str,
    build_type: str,
) -> dict:
    """Extract features from one compiled object file and assemble a row.

    Every scalar feature `analysis.features.extract_features()` returns
    is included automatically (see `_flatten_scalar_features`), so
    newly added features (Phase 6+) appear in the dataset without this
    function needing to be edited each time.
    """
    features = extract_features(binary_path)

    row = {
        "binary_name": binary_path.name,
        "project": project_name,
        "algorithm_label": algorithm_label,
        "optimization_level": optimization_level,
        "compiler": compiler,
        "compiler_version": compiler_version,
        "build_type": build_type,
        "build_system": "direct_compile",
        "binary_type": "object",
        "crypto_library": project_name,
    }
    row.update(_flatten_scalar_features(features))
    row["architecture"] = features.get("architecture") or architecture
    row["import_libraries"] = _stringify_import_libraries(features.get("import_libraries"))
    return row


def run_object_pipeline(
    project_name: str,
    source_dir: Path,
    optimization_levels: list[str],
    build_types: list[str],
    compilers: list[str],
    summary: PipelineSummary,
    max_files_per_project: Optional[int] = None,
) -> list[dict]:
    """Compile every discovered algorithm source file across every build
    variant (optimization level x build type x compiler) and extract
    features from each resulting object file (Phase 2B).

    A single source file failing to compile under a given variant (e.g.
    a missing generated config header) is logged and skipped; it never
    stops processing of the remaining files, variants, or projects.
    """
    rows: list[dict] = []

    algorithm_sources = discover_algorithm_source_files(source_dir)
    if not algorithm_sources:
        logger.warning("[%s] No algorithm-level source files discovered; skipping object pipeline.", project_name)
        return rows

    include_dirs = discover_header_include_dirs(source_dir)
    compiler_versions = {c: _get_compiler_version(c) for c in compilers}

    object_output_root = config.COMPILED_DIR / project_name / "objects"

    files_processed = 0
    for algorithm, source_files in algorithm_sources.items():
        summary.algorithms_detected.add(algorithm)
        for source_file in source_files:
            if max_files_per_project is not None and files_processed >= max_files_per_project:
                logger.info(
                    "[%s] Reached max_files_per_project=%d for this run; "
                    "remaining source files will be processed on a future run.",
                    project_name, max_files_per_project,
                )
                return rows
            files_processed += 1

            for compiler in compilers:
                for optimization_level in optimization_levels:
                    for build_type in build_types:
                        object_name = (
                            f"{source_file.stem}__{compiler}_{optimization_level}_{build_type}.o"
                        )
                        output_path = object_output_root / algorithm / object_name

                        success, error_message = compile_object_file(
                            source_file=source_file,
                            include_dirs=include_dirs,
                            compiler=compiler,
                            optimization_level=optimization_level,
                            build_type=build_type,
                            output_path=output_path,
                        )

                        if not success:
                            summary.objects_failed += 1
                            logger.debug(
                                "[%s] Skipped %s (%s/%s/%s): %s",
                                project_name, source_file.name, compiler,
                                optimization_level, build_type, error_message,
                            )
                            continue

                        summary.objects_compiled += 1
                        logger.info(
                            "[%s] Compiled %s -> %s (%s, %s, %s)",
                            project_name, source_file.name, output_path.name,
                            compiler, optimization_level, build_type,
                        )

                        row = build_object_dataset_row(
                            binary_path=output_path,
                            project_name=project_name,
                            algorithm_label=algorithm,
                            architecture=config.HOST_ARCHITECTURE,
                            optimization_level=optimization_level,
                            compiler=compiler,
                            compiler_version=compiler_versions.get(compiler, "unknown"),
                            build_type=build_type,
                        )
                        rows.append(row)

    logger.info(
        "[%s] Object pipeline complete: %d objects compiled, %d skipped/failed.",
        project_name, summary.objects_compiled, summary.objects_failed,
    )
    return rows


# ---------------------------------------------------------------------------
# Step 5 + 6: Whole-binary feature extraction -> dataset rows (Phase 2A)
# ---------------------------------------------------------------------------

def build_dataset_row(
    binary_path: Path,
    project_name: str,
    optimization_level: str,
    architecture: str,
    compiler: str,
    compiler_version: str,
    build_system: str,
) -> dict:
    """Extract features from one whole-library binary and assemble a row.

    Every scalar feature `analysis.features.extract_features()` returns
    is included automatically (see `_flatten_scalar_features`), so
    newly added features (Phase 6+) appear in the dataset without this
    function needing to be edited each time.
    """
    logger.info("Extracting features from %s", binary_path)
    features = extract_features(binary_path)
    label = infer_label(binary_path, project_name, features)

    row = {
        "binary_name": binary_path.name,
        "project": project_name,
        "algorithm_label": label,
        "optimization_level": optimization_level,
        "compiler": compiler,
        "compiler_version": compiler_version,
        "build_type": "release",
        "build_system": build_system,
        "binary_type": _classify_binary_type(binary_path),
        "crypto_library": project_name,
    }
    row.update(_flatten_scalar_features(features))
    row["architecture"] = features.get("architecture") or architecture
    row["import_libraries"] = _stringify_import_libraries(features.get("import_libraries"))
    return row


# ---------------------------------------------------------------------------
# Step 8 + 9: Dataset + metadata output
# ---------------------------------------------------------------------------

# Identifier/metadata columns always placed first (for a readable CSV);
# every other column present in the generated rows -- including any new
# feature added to `analysis/features.py` -- is appended automatically,
# so this list never needs to be hand-updated when features are added.
_DATASET_IDENTIFIER_COLUMNS: list[str] = [
    "binary_name", "project", "algorithm_label", "architecture",
    "optimization_level", "compiler", "compiler_version", "build_type",
    "build_system", "binary_type", "crypto_library",
]


def write_dataset_csv(rows: list[dict]) -> Path:
    """Write the accumulated dataset rows to dataset/data/raw/dataset.csv."""
    output_path = config.RAW_DATA_DIR / "dataset.csv"
    if not rows:
        logger.warning("No dataset rows were generated; writing an empty dataset.csv with headers only.")
        pd.DataFrame(columns=_DATASET_IDENTIFIER_COLUMNS).to_csv(output_path, index=False)
        return output_path

    dataframe = pd.DataFrame(rows)
    for column in _DATASET_IDENTIFIER_COLUMNS:
        if column not in dataframe.columns:
            dataframe[column] = None

    feature_columns = sorted(c for c in dataframe.columns if c not in _DATASET_IDENTIFIER_COLUMNS)
    dataframe = dataframe[_DATASET_IDENTIFIER_COLUMNS + feature_columns]

    before = len(dataframe)
    dataframe = dataframe.drop_duplicates()
    removed = before - len(dataframe)
    if removed:
        logger.info("Removed %d exact-duplicate row(s) before writing dataset.csv.", removed)

    dataframe.to_csv(output_path, index=False)
    logger.info("Wrote %d rows to %s", len(dataframe), output_path)
    return output_path


def write_dataset_metadata(
    summary: PipelineSummary,
    architectures_used: list[str],
    compilers_used: list[str],
    optimization_levels_used: list[str],
    build_types_used: list[str],
) -> Path:
    """Write dataset/data/raw/dataset_metadata.json describing this run."""
    dataset_csv_path = config.RAW_DATA_DIR / "dataset.csv"
    total_samples = 0
    total_unique_binaries = 0
    total_features = None

    if dataset_csv_path.exists():
        try:
            dataframe = pd.read_csv(dataset_csv_path)
            total_samples = len(dataframe)
            total_unique_binaries = dataframe["binary_name"].nunique() if "binary_name" in dataframe.columns else total_samples
            non_feature_columns = {"binary_name", "project", "algorithm_label", "crypto_library"}
            total_features = len([c for c in dataframe.columns if c not in non_feature_columns])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not compute dataset statistics from dataset.csv: %s", exc)

    metadata = {
        "dataset_version": config.DATASET_VERSION,
        "generation_date": datetime.now(timezone.utc).isoformat(),
        "generation_duration_seconds": round(time.monotonic() - summary.started_at, 2),
        "projects_used": [
            config.PROJECTS[name]["display_name"]
            for name in summary.successful_projects
            if name in config.PROJECTS
        ],
        "algorithms_detected": sorted(summary.algorithms_detected),
        "compiler_versions": compilers_used,
        "optimization_levels": optimization_levels_used,
        "build_types": build_types_used,
        "architectures": architectures_used,
        "total_binaries": summary.total_binaries_processed + summary.objects_compiled,
        "total_samples": total_samples,
        "total_unique_binaries": total_unique_binaries,
        "total_features": total_features,
    }

    metadata_path = config.RAW_DATA_DIR / "dataset_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    logger.info("Wrote dataset metadata to %s", metadata_path)
    return metadata_path


# ---------------------------------------------------------------------------
# Pipeline orchestration
# ---------------------------------------------------------------------------

def run_pipeline(
    projects: Optional[list[str]] = None,
    optimization_levels: Optional[list[str]] = None,
    architecture: str = config.HOST_ARCHITECTURE,
    build_types: Optional[list[str]] = None,
    compilers: Optional[list[str]] = None,
    run_library_level: bool = True,
    run_object_level: bool = True,
    max_object_files_per_project: Optional[int] = None,
) -> PipelineSummary:
    """Run the full offline dataset-generation pipeline end to end.

    Args:
        projects: Subset of project keys from `config.PROJECTS` to build.
            Defaults to all configured projects.
        optimization_levels: Subset of optimization levels to build.
            Defaults to all levels in `config.OPTIMIZATION_LEVELS`.
        architecture: Target architecture; must be a host-supported
            architecture from `config.SUPPORTED_ARCHITECTURES`.
        build_types: Subset of `config.BUILD_TYPES` keys used for the
            Phase 2B object-file pipeline. Defaults to all of them.
        compilers: Subset of compilers to use for the object-file
            pipeline. Defaults to every compiler actually available on
            this machine (auto-detected).
        run_library_level: Whether to run the Phase 2A whole-library
            build pipeline.
        run_object_level: Whether to run the Phase 2B per-algorithm
            object-file compilation pipeline.
        max_object_files_per_project: Optional cap on the number of
            distinct algorithm source files compiled per project, useful
            for a bounded smoke-test run. Leave as None for a full,
            unbounded research-grade run.

    Returns:
        A `PipelineSummary` describing what succeeded/failed.
    """
    projects = projects or list(config.PROJECTS.keys())
    optimization_levels = optimization_levels or config.OPTIMIZATION_LEVELS
    build_types = build_types or list(config.BUILD_TYPES.keys())
    compilers = compilers or get_available_compilers()

    if architecture not in config.SUPPORTED_ARCHITECTURES:
        raise ValueError(
            f"Architecture '{architecture}' is not enabled. "
            f"Supported: {config.SUPPORTED_ARCHITECTURES}"
        )
    if not compilers:
        logger.error("No compilers available; the object-level pipeline will be skipped.")

    logger.info(
        "Target dataset size: %d-%d real samples (see config.TARGET_SAMPLE_COUNT_MIN/MAX).",
        config.TARGET_SAMPLE_COUNT_MIN, config.TARGET_SAMPLE_COUNT_MAX,
    )

    summary = PipelineSummary()
    all_rows: list[dict] = []
    compiler_versions_seen: set[str] = set()

    for project_name in projects:
        if project_name not in config.PROJECTS:
            logger.error("Unknown project '%s' -- skipping.", project_name)
            summary.failed_projects[project_name] = "Not found in config.PROJECTS"
            continue

        project_cfg = config.PROJECTS[project_name]
        logger.info("=== Processing project: %s ===", project_cfg["display_name"])

        source_dir = clone_repository(project_name, project_cfg)
        if source_dir is None:
            summary.failed_projects[project_name] = "Clone failed"
            continue

        project_had_any_success = False

        # --- Phase 2A: whole-library builds -------------------------------
        if run_library_level:
            for optimization_level in optimization_levels:
                build_result = build_project(
                    project_name, project_cfg, source_dir, optimization_level, architecture
                )
                summary.build_results.append(build_result)

                if not build_result.success:
                    continue

                compiler_versions_seen.add(_get_compiler_version(
                    f"{config.ARCHITECTURE_TOOLCHAINS.get(architecture, {}).get('cc_prefix') or ''}"
                    f"{project_cfg.get('compiler', config.DEFAULT_COMPILER)}"
                ))

                binaries = discover_binaries(source_dir)
                if not binaries:
                    logger.warning(
                        "[%s] Build reported success at %s but no binaries were discovered.",
                        project_name, optimization_level,
                    )
                    continue

                copied_binaries = copy_binaries_to_compiled(
                    project_name, optimization_level, architecture, binaries
                )
                build_result.binaries_found = len(copied_binaries)
                summary.total_binaries_processed += len(copied_binaries)
                project_had_any_success = True

                for binary_path in copied_binaries:
                    row = build_dataset_row(
                        binary_path=binary_path,
                        project_name=project_name,
                        optimization_level=optimization_level,
                        architecture=architecture,
                        compiler=project_cfg.get("compiler", config.DEFAULT_COMPILER),
                        compiler_version=_get_compiler_version(project_cfg.get("compiler", config.DEFAULT_COMPILER)),
                        build_system=detect_build_system(source_dir, project_cfg.get("build_system", "make")),
                    )
                    all_rows.append(row)

        # --- Phase 2B: per-algorithm object-file compilation ---------------
        if run_object_level and compilers:
            object_rows = run_object_pipeline(
                project_name=project_name,
                source_dir=source_dir,
                optimization_levels=optimization_levels,
                build_types=build_types,
                compilers=compilers,
                summary=summary,
                max_files_per_project=max_object_files_per_project,
            )
            if object_rows:
                project_had_any_success = True
            all_rows.extend(object_rows)
            for compiler in compilers:
                compiler_versions_seen.add(_get_compiler_version(compiler))

        if project_had_any_success:
            summary.successful_projects.add(project_name)
        else:
            summary.failed_projects[project_name] = "No optimization level or algorithm source file built successfully"

    write_dataset_csv(all_rows)
    summary.total_dataset_rows = len(all_rows)
    write_dataset_metadata(
        summary,
        architectures_used=[architecture],
        compilers_used=sorted(compiler_versions_seen) or ["unknown"],
        optimization_levels_used=optimization_levels,
        build_types_used=build_types,
    )

    return summary


def _print_summary(summary: PipelineSummary) -> None:
    """Print the final pipeline summary to stdout/log."""
    duration = time.monotonic() - summary.started_at
    logger.info("")
    logger.info("================= DATASET BUILD SUMMARY =================")
    logger.info("Successful projects: %s", sorted(summary.successful_projects) or "none")
    logger.info("Failed projects:")
    if summary.failed_projects:
        for project, reason in summary.failed_projects.items():
            logger.info("  - %s: %s", project, reason)
    else:
        logger.info("  none")
    logger.info("Algorithms detected: %s", sorted(summary.algorithms_detected) or "none")
    logger.info("Total library-level binaries processed: %d", summary.total_binaries_processed)
    logger.info("Total algorithm-level objects compiled: %d", summary.objects_compiled)
    logger.info("Total algorithm-level objects skipped/failed: %d", summary.objects_failed)
    logger.info("Total dataset rows generated: %d", summary.total_dataset_rows)
    logger.info("Total run duration: %.1fs", duration)
    logger.info("===========================================================")


def main() -> None:
    """Entry point for running the dataset builder as a script."""
    log_path = _configure_logging()
    logger.info("Dataset build log: %s", log_path)
    summary = run_pipeline()
    _print_summary(summary)


if __name__ == "__main__":
    main()
