---
title: NIST SP 800-131A — Transitioning the Use of Cryptographic Algorithms and Key Lengths
source_type: NIST
identifier: SP 800-131A Rev. 2
---

# Transitioning Cryptographic Algorithms and Key Lengths

NIST SP 800-131A documents the transition schedule under which
specific cryptographic algorithms and key lengths move from
"acceptable" to "deprecated" to "disallowed" for U.S. federal use. It
is the primary NIST reference for identifying which algorithms are
considered obsolete.

Algorithms and constructions explicitly deprecated or disallowed under
this guidance include: DES (single-key, 56-bit) -- disallowed for
encryption; two-key Triple DES -- disallowed; SHA-1 -- disallowed for
digital signature generation and deprecated generally, though it may
still appear in some legacy non-signature contexts; and RC4, which was
never NIST-approved and is widely considered broken due to statistical
biases in its keystream. MD5 is not a NIST-approved hash function at
all and is considered cryptographically broken for collision
resistance, making it unsuitable for digital signatures, certificate
validation, or integrity verification of untrusted data.

The publication recommends organizations identify and inventory use of
these deprecated primitives and migrate to NIST-approved replacements
(e.g. AES for DES/3DES, SHA-256/SHA-3 for SHA-1/MD5) according to a
documented transition plan.
