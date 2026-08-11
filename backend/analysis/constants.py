"""
analysis/constants.py

Centralized database of cryptographic signatures used throughout the
Firmware Analysis Engine.

This is the single source of truth for "what does AES/DES/RSA/etc. look
like inside a compiled binary" -- both the offline Dataset Builder
(Phase 2) and the runtime firmware analysis pipeline (Phase 4) detect
crypto evidence by importing from this module, so the two never drift
apart.

Three kinds of evidence are catalogued:

1. `CRYPTO_MAGIC_CONSTANTS` -- fixed byte sequences (S-boxes, hash
   initialization vectors, well-known constant strings) that appear
   verbatim in a compiled binary regardless of symbol stripping.
2. `CRYPTO_SYMBOL_KEYWORDS` -- substrings checked against symbol,
   import, and export names (works only on non-stripped binaries, but
   catches algorithms with no fixed byte-level constant, like RSA/ECC).
3. `KNOWN_CRYPTO_LIBRARY_NAMES` -- substrings checked against imported
   *library* names (e.g. `libcrypto.so`), used as secondary evidence
   that a binary links against a known cryptographic library.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# 1. Known magic constants (S-boxes, hash IVs, well-known constant strings)
# --------------------------------------------------------------------------
#
# Each value is raw bytes that can be searched for verbatim within a
# binary's contents. Keys are the canonical algorithm labels used
# throughout CryptoSage (matching the Phase 2 dataset schema).

CRYPTO_MAGIC_CONSTANTS: dict[str, bytes] = {
    # First 16 bytes of the classic AES (Rijndael) forward S-box.
    "AES": bytes([
        0x63, 0x7C, 0x77, 0x7B, 0xF2, 0x6B, 0x6F, 0xC5,
        0x30, 0x01, 0x67, 0x2B, 0xFE, 0xD7, 0xAB, 0x76,
    ]),
    # SHA-1 initial hash values (H0, H1 as 32-bit big-endian words).
    "SHA1": bytes.fromhex("67452301efcdab89"),
    # SHA-224 initial hash value (distinct from SHA-256's).
    "SHA224": bytes.fromhex("c1059ed8367cd507"),
    # SHA-256 initial hash values (H0, H1).
    "SHA256": bytes.fromhex("6a09e667bb67ae85"),
    # SHA-384 initial hash value (distinct from SHA-512's).
    "SHA384": bytes.fromhex("cbbb9d5dc1059ed8"),
    # SHA-512 initial hash values (H0 as a 64-bit big-endian word).
    "SHA512": bytes.fromhex("6a09e667f3bcc908"),
    # MD5 initial state words (A, B, C, D as 32-bit little-endian words).
    "MD5": bytes.fromhex("0123456789abcdeffedcba9876543210"),
    # ChaCha20/Salsa20 constant "expand 32-byte k" used with 256-bit keys.
    "ChaCha20": b"expand 32-byte k",
    # First 8 bytes of the Blowfish P-array (digits of pi in hex).
    "Blowfish": bytes.fromhex("243f6a8885a308d3"),
}

# --------------------------------------------------------------------------
# 2. Symbol/import/export keyword evidence
# --------------------------------------------------------------------------
#
# Substrings (case-insensitive) checked against symbol names, imported
# function names, and exported function names. A match is evidence the
# binary implements or calls into an implementation of that algorithm.

CRYPTO_SYMBOL_KEYWORDS: dict[str, list[str]] = {
    "AES": ["aes_", "AES_", "rijndael", "aes128", "aes192", "aes256"],
    "DES": ["des_", "DES_", "des_encrypt", "des_decrypt"],
    "3DES": ["des3", "3des", "tripledes", "des_ede3"],
    "SHA1": ["sha1", "SHA1"],
    "SHA224": ["sha224", "SHA224"],
    "SHA256": ["sha256", "SHA256"],
    "SHA384": ["sha384", "SHA384"],
    "SHA512": ["sha512", "SHA512"],
    "RSA": ["rsa_", "RSA_", "rsa_verify", "rsa_sign", "rsa_encrypt", "rsa_decrypt"],
    "ECC": ["ec_", "EC_", "ecdsa", "ecdh", "ed25519", "curve25519", "x25519"],
    "ChaCha20": ["chacha", "salsa20"],
    "Poly1305": ["poly1305"],
    "RC4": ["rc4", "arcfour"],
    "Blowfish": ["blowfish"],
    "Twofish": ["twofish"],
    "Camellia": ["camellia"],
}

# --------------------------------------------------------------------------
# 3. Known cryptographic library names
# --------------------------------------------------------------------------
#
# Substrings checked against imported *library* names (e.g. from an
# ELF's DT_NEEDED entries). Presence is secondary evidence: a binary
# that links libcrypto.so almost certainly uses cryptographic code, even
# if none of its own symbols mention a specific algorithm by name.

KNOWN_CRYPTO_LIBRARY_NAMES: list[str] = [
    "libcrypto", "libssl", "libsodium", "libmbedcrypto", "libmbedtls",
    "libmbedx509", "libwolfssl", "libtomcrypt", "libtommath", "libgcrypt",
    "libnettle", "libhogweed", "libgnutls",
]

# All canonical algorithm labels this constants database has evidence
# for, in the order used across the dataset (kept in sync with
# `dataset/config.py`'s `ALGORITHM_SOURCE_KEYWORDS` label set).
KNOWN_ALGORITHM_LABELS: list[str] = [
    "AES", "DES", "3DES", "SHA1", "SHA224", "SHA256", "SHA384", "SHA512",
    "RSA", "ECC", "ChaCha20", "Poly1305", "RC4", "Blowfish", "Twofish",
    "Camellia",
]

# --------------------------------------------------------------------------
# 4. RSA / ECC signatures (Phase 6 -- research-grade feature engineering)
# --------------------------------------------------------------------------
#
# RSA and ECC have no fixed S-box-style magic constant, but real-world
# implementations do embed a handful of recognizable byte patterns:
# the near-universal public exponent 65537, and the DER-encoded object
# identifiers (OIDs) of the small set of standardized elliptic curves
# almost every implementation supports.

# The RSA public exponent 65537 (0x010001), as it appears either as a
# raw 3-byte big-endian integer or as a DER INTEGER encoding (with a
# leading 0x00 padding byte when the high bit would otherwise be set).
RSA_COMMON_EXPONENTS: dict[str, bytes] = {
    "65537_raw": bytes.fromhex("010001"),
    "65537_der": bytes.fromhex("00010001"),
}

# DER-encoded OIDs for the elliptic curves supported by essentially
# every TLS/crypto library: secp256r1/P-256, secp384r1/P-384,
# secp521r1/P-521, and secp256k1 (Bitcoin/Ethereum).
ECC_CURVE_OIDS: dict[str, bytes] = {
    "P-256": bytes.fromhex("2a8648ce3d030107"),       # 1.2.840.10045.3.1.7
    "P-384": bytes.fromhex("2b81040022"),               # 1.3.132.0.34
    "P-521": bytes.fromhex("2b81040023"),               # 1.3.132.0.35
    "secp256k1": bytes.fromhex("2b8104000a"),           # 1.3.132.0.10
}

# --------------------------------------------------------------------------
# 5. Cryptographic family taxonomy (Phase 6 -- hierarchical classification)
# --------------------------------------------------------------------------
#
# Maps every algorithm label produced by the Dataset Builder to a
# higher-level cryptographic family, used by the Stage-1 classifier in
# `ml/train.py` / `ml/predict.py`. The five families named in the
# CryptoSage specification (Symmetric Encryption, Hash Functions,
# Public Key Cryptography, Message Authentication, Stream Cipher) are
# extended with one additional, honestly-labeled family, "Key
# Derivation", for the KDF algorithms (Argon2, PBKDF2, HKDF) the
# Dataset Builder genuinely produces samples for -- forcing these into
# one of the other five families would misrepresent what they are.

ALGORITHM_FAMILIES: dict[str, str] = {
    # Symmetric Encryption (block ciphers)
    "AES": "Symmetric Encryption",
    "DES": "Symmetric Encryption",
    "3DES": "Symmetric Encryption",
    "Blowfish": "Symmetric Encryption",
    "Twofish": "Symmetric Encryption",
    "Camellia": "Symmetric Encryption",
    # Stream Cipher
    "ChaCha20": "Stream Cipher",
    "RC4": "Stream Cipher",
    # Hash Functions
    "SHA1": "Hash Functions",
    "SHA224": "Hash Functions",
    "SHA256": "Hash Functions",
    "SHA384": "Hash Functions",
    "SHA512": "Hash Functions",
    "SHA3": "Hash Functions",
    "MD5": "Hash Functions",
    # Message Authentication
    "HMAC": "Message Authentication",
    "Poly1305": "Message Authentication",
    # Public Key Cryptography
    "RSA": "Public Key Cryptography",
    "ECC": "Public Key Cryptography",
    "X25519": "Public Key Cryptography",
    "Ed25519": "Public Key Cryptography",
    # Key Derivation (pragmatic extension -- see docstring above)
    "Argon2": "Key Derivation",
    "PBKDF2": "Key Derivation",
    "HKDF": "Key Derivation",
}

# Canonical, ordered family list (used for consistent reporting/plots).
KNOWN_FAMILIES: list[str] = [
    "Symmetric Encryption", "Stream Cipher", "Hash Functions",
    "Message Authentication", "Public Key Cryptography", "Key Derivation",
]
