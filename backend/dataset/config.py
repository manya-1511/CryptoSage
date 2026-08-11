"""
dataset/config.py

Central configuration for the Phase 2A offline dataset builder pipeline.

Every value that could change between environments or research runs
(which projects to build, which optimization levels, which compilers,
which architectures, which crypto signatures to look for) lives here.
`builder.py`, `extractor.py`, and `preprocess.py` read from this module
instead of hardcoding paths, URLs, or build commands, so that adding a
new project, compiler, optimization level, or architecture in the
future is a configuration change, not a code change.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

# --------------------------------------------------------------------------
# Base paths
# --------------------------------------------------------------------------

# Root of the `dataset/` package (this file's directory).
DATASET_DIR: Path = Path(__file__).resolve().parent

SOURCES_DIR: Path = DATASET_DIR / "sources"
COMPILED_DIR: Path = DATASET_DIR / "compiled"
DATA_DIR: Path = DATASET_DIR / "data"
RAW_DATA_DIR: Path = DATA_DIR / "raw"
PROCESSED_DATA_DIR: Path = DATA_DIR / "processed"
FEATURES_DATA_DIR: Path = DATA_DIR / "features"
LOGS_DIR: Path = DATASET_DIR / "logs"

for _dir in (
    SOURCES_DIR,
    COMPILED_DIR,
    RAW_DATA_DIR,
    PROCESSED_DATA_DIR,
    FEATURES_DATA_DIR,
    LOGS_DIR,
):
    _dir.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------
# Dataset versioning
# --------------------------------------------------------------------------

DATASET_VERSION: str = "1.0"

# --------------------------------------------------------------------------
# Optimization levels
# --------------------------------------------------------------------------

# Every supported project is built once per optimization level so the
# resulting dataset captures how compiler optimization changes a
# binary's static footprint.
OPTIMIZATION_LEVELS: list[str] = ["O0", "O1", "O2", "O3"]

# --------------------------------------------------------------------------
# Architectures
# --------------------------------------------------------------------------

# Phase 2A fully supports the host architecture only. Additional entries
# can be added here later (each needs a working cross-compiler configured
# in COMPILERS below) without touching builder.py's logic.
HOST_ARCHITECTURE: str = "x86_64"
SUPPORTED_ARCHITECTURES: list[str] = ["x86_64"]

# Maps an architecture name to the compiler prefix/flags needed to target
# it. Cross-architectures are listed for future readiness but are not
# enabled unless a toolchain is actually present on the machine running
# the builder (checked at runtime in builder.py).
ARCHITECTURE_TOOLCHAINS: dict[str, dict[str, Optional[str]]] = {
    "x86_64": {"cc_prefix": "", "extra_cflags": ""},
    # Future: install `gcc-arm-linux-gnueabihf` and uncomment.
    # "arm": {"cc_prefix": "arm-linux-gnueabihf-", "extra_cflags": ""},
    # Future: install `gcc-aarch64-linux-gnu` and uncomment.
    # "arm64": {"cc_prefix": "aarch64-linux-gnu-", "extra_cflags": ""},
    # Future: install a MIPS cross-compiler and uncomment.
    # "mips": {"cc_prefix": "mips-linux-gnu-", "extra_cflags": ""},
}

# --------------------------------------------------------------------------
# Compilers
# --------------------------------------------------------------------------

# The default compiler used for the host architecture build. `gcc` is
# preferred for maximum compatibility with the projects' build systems;
# `clang` is supported as an alternative and can be selected per project
# below if desired.
DEFAULT_COMPILER: str = "gcc"
SUPPORTED_COMPILERS: list[str] = ["gcc", "clang"]

# --------------------------------------------------------------------------
# Project definitions
# --------------------------------------------------------------------------
#
# `build_system` is a hint used before auto-detection falls back to
# inspecting the repository; `configure_args` / `cmake_args` are extra
# flags appended to the respective build command (kept minimal so builds
# stay fast and portable across environments).

PROJECTS: dict[str, dict] = {
    "openssl": {
        "display_name": "OpenSSL",
        "repo_url": "https://github.com/openssl/openssl.git",
        "build_system": "autotools",  # uses ./Configure, autotools-like
        "configure_cmd": "./Configure",
        "configure_args": ["linux-x86_64"],
        "cmake_args": [],
        "compiler": "gcc",
        "expected_algorithms": [
            "AES", "RSA", "SHA256", "SHA1", "ECC", "DES", "3DES",
            "ChaCha20", "Blowfish", "RC4",
        ],
    },
    "mbedtls": {
        "display_name": "mbedTLS",
        "repo_url": "https://github.com/Mbed-TLS/mbedtls.git",
        "build_system": "cmake",
        "configure_cmd": None,
        "configure_args": [],
        "cmake_args": ["-DENABLE_TESTING=OFF", "-DENABLE_PROGRAMS=ON"],
        "compiler": "gcc",
        "expected_algorithms": [
            "AES", "RSA", "SHA256", "ECC", "DES", "3DES", "ChaCha20",
        ],
    },
    "wolfssl": {
        "display_name": "WolfSSL",
        "repo_url": "https://github.com/wolfSSL/wolfssl.git",
        "build_system": "autotools",
        "configure_cmd": "./autogen.sh && ./configure",
        "configure_args": [],
        "cmake_args": [],
        "compiler": "gcc",
        "expected_algorithms": [
            "AES", "RSA", "SHA256", "ECC", "ChaCha20", "DES", "3DES",
        ],
    },
    "libtomcrypt": {
        "display_name": "LibTomCrypt",
        "repo_url": "https://github.com/libtom/libtomcrypt.git",
        "build_system": "make",
        # LibTomCrypt's default `makefile` only produces a static
        # archive (.a); `makefile.shared` builds the shared object
        # (.so) we actually want to include as a dataset sample.
        "make_file": "makefile.shared",
        "configure_cmd": None,
        "configure_args": [],
        "cmake_args": [],
        "compiler": "gcc",
        "expected_algorithms": [
            "AES", "RSA", "SHA256", "DES", "3DES", "RC4", "Blowfish",
            "ChaCha20",
        ],
    },
    "libsodium": {
        "display_name": "Libsodium",
        "repo_url": "https://github.com/jedisct1/libsodium.git",
        "build_system": "autotools",
        "configure_cmd": "./autogen.sh -s && ./configure",
        "configure_args": [],
        "cmake_args": [],
        "compiler": "gcc",
        "expected_algorithms": ["ChaCha20", "AES", "SHA256", "ECC"],
    },
}

# --------------------------------------------------------------------------
# Binary discovery
# --------------------------------------------------------------------------

# Directory name fragments to skip while walking a build tree for
# binaries — documentation, examples, and test artifacts are not
# representative of production cryptographic code paths.
IGNORED_DIR_KEYWORDS: list[str] = [
    "doc", "docs", "test", "tests", "example", "examples",
    "sample", "samples", "demo", "demos", ".git",
]

# File extensions that are never binaries of interest even if they pass
# the ELF magic-byte check (defensive; ELF check is the primary filter).
IGNORED_EXTENSIONS: set[str] = {".o", ".a", ".la", ".lo", ".txt", ".md", ".cmake"}

# ELF magic bytes used to positively identify a compiled binary.
ELF_MAGIC: bytes = b"\x7fELF"

# --------------------------------------------------------------------------
# Crypto label inference
# --------------------------------------------------------------------------

# Keyword -> canonical label. Checked (case-insensitively) against the
# binary's filename, its containing project/source path, and its
# imported/exported symbol names, in that priority order. Used for
# whole-binary (library/executable) labeling.
ALGORITHM_KEYWORDS: dict[str, str] = {
    "aes": "AES",
    "rijndael": "AES",
    "sha256": "SHA256",
    "sha-256": "SHA256",
    "sha1": "SHA1",
    "sha-1": "SHA1",
    "rsa": "RSA",
    "ecdsa": "ECC",
    "ecdh": "ECC",
    "ec_": "ECC",
    "ecc": "ECC",
    "curve25519": "ECC",
    "ed25519": "ECC",
    "chacha20": "ChaCha20",
    "chacha": "ChaCha20",
    "salsa20": "ChaCha20",
    "blowfish": "Blowfish",
    "rc4": "RC4",
    "arcfour": "RC4",
    "des3": "3DES",
    "3des": "3DES",
    "tripledes": "3DES",
    "des": "DES",
}

# Fallback label when no algorithm signature is detected anywhere.
NON_CRYPTO_LABEL: str = "NON_CRYPTO"

# --------------------------------------------------------------------------
# Algorithm-level source discovery (Phase 2B)
# --------------------------------------------------------------------------
#
# Ordered (keyword, label) pairs used to identify which cryptographic
# algorithm a single *source file* implements, so individual algorithm
# implementations -- not whole libraries -- become dataset samples.
# Order matters: more specific keywords are listed before more general
# ones (e.g. "3des" before "des") so the first match wins.
#
# Matching strategy (see builder.py `_match_algorithm_from_filename`):
#   1. Exact match against a filename token (safest -- avoids false
#      positives such as "aes_desc.c" being mistaken for DES).
#   2. Substring match against the full filename stem, but ONLY for
#      keywords of length >= `MIN_SUBSTRING_KEYWORD_LENGTH`, to catch
#      compound filenames (e.g. "chacha20poly1305_encrypt.c") without
#      risking short, ambiguous keywords matching unrelated files.

ALGORITHM_SOURCE_KEYWORDS: list[tuple[str, str]] = [
    ("ed25519", "Ed25519"),
    ("x25519", "X25519"),
    ("curve25519", "X25519"),
    ("ecdsa", "ECC"),
    ("ecdh", "ECC"),
    ("ecc", "ECC"),
    ("rsa", "RSA"),
    ("tripledes", "3DES"),
    ("3des", "3DES"),
    ("des3", "3DES"),
    ("aes128", "AES"),
    ("aes192", "AES"),
    ("aes256", "AES"),
    ("aesni", "AES"),
    ("aesce", "AES"),
    ("rijndael", "AES"),
    ("aes", "AES"),
    ("twofish", "Twofish"),
    ("blowfish", "Blowfish"),
    ("camellia", "Camellia"),
    ("arcfour", "RC4"),
    ("rc4", "RC4"),
    ("chachapoly", "ChaCha20"),
    ("chacha20", "ChaCha20"),
    ("chacha", "ChaCha20"),
    ("salsa20", "ChaCha20"),
    ("poly1305", "Poly1305"),
    ("sha224", "SHA224"),
    ("sha256", "SHA256"),
    ("sha384", "SHA384"),
    ("sha512", "SHA512"),
    ("sha3", "SHA3"),
    ("sha1", "SHA1"),
    ("md5", "MD5"),
    ("hmac", "HMAC"),
    ("pbkdf2", "PBKDF2"),
    ("hkdf", "HKDF"),
    ("argon2", "Argon2"),
    ("des", "DES"),
    ("ec", "ECC"),
]

# Substring fallback is only applied for keywords at least this long, to
# avoid short/ambiguous keywords (e.g. "des", "ec", "rc4") matching
# unrelated filenames via simple substring containment.
MIN_SUBSTRING_KEYWORD_LENGTH: int = 5

# File-stem fragments that indicate a file is a test/demo/fuzz harness
# rather than a real algorithm implementation, even if it lives outside
# an ignored directory. These are excluded from algorithm-level source
# discovery (Phase 2B), consistent with "skip test programs" guidance.
NON_IMPLEMENTATION_FILENAME_MARKERS: list[str] = [
    "_test", "test_", "_fuzz", "fuzz_", "_bench", "bench_", "_demo", "demo_",
]

# Compilers to attempt for the Phase 2B per-algorithm object-file pipeline.
# Availability is checked at runtime (`shutil.which`); an unavailable
# compiler is skipped and logged, never causing the run to fail.
OBJECT_PIPELINE_COMPILERS: list[str] = ["gcc", "clang"]

# Build types layered on top of optimization level for the object-file
# pipeline: each maps to extra compiler flags applied in addition to
# `-O<level>`. Optimization level and build type are recorded as
# separate dataset columns.
BUILD_TYPES: dict[str, list[str]] = {
    "debug": ["-g", "-DDEBUG"],
    "release": ["-DNDEBUG"],
}

# Maximum number of "-I<dir>" flags passed when compiling a standalone
# object file. Every directory under a project's source tree containing
# at least one header file is discovered automatically (no hardcoded
# per-project include paths) and capped at this count to keep build
# commands manageable.
MAX_INCLUDE_DIRS: int = 200

# Approximate target dataset size this framework is designed to reach
# when run against all configured projects/compilers/optimization
# levels/build types. Not an early-stop threshold -- the pipeline always
# processes every discovered algorithm source file; this constant is
# used only for logging/progress reporting.
TARGET_SAMPLE_COUNT_MIN: int = 5000
TARGET_SAMPLE_COUNT_MAX: int = 7000


# Known static byte-level crypto constants used as strong positive
# signals (independent of symbol names, so they also work on stripped
# binaries). Each entry is (label, hex-bytes-as-python-bytes).
CRYPTO_CONSTANT_SIGNATURES: dict[str, bytes] = {
    # First 16 bytes of the classic AES forward S-box.
    "aes_constant": bytes([
        0x63, 0x7C, 0x77, 0x7B, 0xF2, 0x6B, 0x6F, 0xC5,
        0x30, 0x01, 0x67, 0x2B, 0xFE, 0xD7, 0xAB, 0x76,
    ]),
    # SHA-256 initial hash values (first two 32-bit words, big-endian).
    "sha_constant": bytes.fromhex("6a09e667bb67ae85"),
    # SHA-1 initial hash value H0.
    "sha1_constant": bytes.fromhex("67452301efcdab89"),
    # MD5 initial state words.
    "md5_constant": bytes.fromhex("0123456789abcdeffedcba9876543210"),
}

# Symbol-name substrings that indicate a specific crypto primitive is
# linked into a binary, independent of the label-inference keywords
# above (used for the dedicated boolean feature columns).
CRYPTO_SYMBOL_PATTERNS: dict[str, list[str]] = {
    "rsa_symbol": ["rsa_", "RSA_", "rsa_verify", "rsa_sign"],
    "ecc_symbol": ["ec_", "EC_", "ecdsa", "ecdh", "ed25519", "curve25519"],
    "aes_symbol": ["aes_", "AES_", "rijndael"],
    "sha_symbol": ["sha1", "sha256", "sha512", "SHA1", "SHA256"],
    "des_symbol": ["des_", "DES_", "3des"],
    "chacha_symbol": ["chacha", "salsa20"],
}

# --------------------------------------------------------------------------
# Misc
# --------------------------------------------------------------------------

# Build timeout (seconds) per project/optimization-level combination, to
# keep a single slow/failed build from hanging the whole pipeline.
BUILD_TIMEOUT_SECONDS: int = 1800

# Number of parallel `make` jobs. Kept configurable in case the host has
# more cores available.
import os as _os  # noqa: E402

MAKE_JOBS: int = max(1, _os.cpu_count() or 1)
