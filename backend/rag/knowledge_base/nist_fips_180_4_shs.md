---
title: NIST FIPS 180-4 — Secure Hash Standard (SHS)
source_type: NIST
identifier: FIPS 180-4
---

# Secure Hash Standard (SHA-1, SHA-2 Family)

FIPS 180-4 specifies the SHA family of hash functions: SHA-1 (160-bit
digest) and the SHA-2 family (SHA-224, SHA-256, SHA-384, SHA-512, and
truncated variants). SHA-1 was found to have practical collision
attacks demonstrated publicly in 2017 (the "SHAttered" attack) and is
disallowed by NIST for digital signature generation; SHA-256, SHA-384,
and SHA-512 remain approved and are the most widely deployed members
of the SHA-2 family for integrity verification, digital signatures,
and as building blocks for HMAC and key derivation functions.

SHA-256 provides a 128-bit security level against collision attacks
under current cryptanalysis and is considered an appropriate default
choice for most new designs requiring a 256-bit-class hash function.
SHA-384 and SHA-512 provide correspondingly larger security margins at
the cost of larger digests and, on 64-bit platforms, comparable or
better performance than SHA-256 due to their 64-bit-word internal
structure.
