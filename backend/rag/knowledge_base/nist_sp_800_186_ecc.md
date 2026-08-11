---
title: NIST SP 800-186 — Recommendations for Discrete Logarithm-based Cryptography (Elliptic Curve Domain Parameters)
source_type: NIST
identifier: SP 800-186
---

# Elliptic Curve Cryptography Domain Parameters

NIST SP 800-186 specifies the approved elliptic curve domain
parameters for U.S. federal use, including the NIST Prime curves
P-224, P-256, P-384, and P-521, as well as (in recent revisions) the
Edwards-curve parameters used by Ed25519/Ed448 and the Montgomery-curve
parameters used by X25519/X448 (originally specified in RFC 7748 and
RFC 8032).

Elliptic curve cryptography (ECC) provides equivalent security to RSA
at substantially smaller key sizes -- a 256-bit ECC key is considered
roughly equivalent in strength to a 3072-bit RSA key -- making it
attractive for constrained/embedded environments. Curve25519-based
constructions (X25519 for key exchange, Ed25519 for signatures) are
widely recommended for new designs due to their resistance to several
implementation-level pitfalls (e.g. invalid-curve attacks, weak
randomness sensitivity) that have historically affected some NIST
Prime curve implementations, alongside their high performance.
