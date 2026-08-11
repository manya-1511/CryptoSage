---
title: RFC 8017 — PKCS #1: RSA Cryptography Specifications
source_type: RFC
identifier: RFC 8017
---

# RSA Cryptography (PKCS #1)

RFC 8017 specifies RSA public-key cryptography as standardized in
PKCS #1, covering RSA encryption/decryption (RSAES-OAEP, the older
RSAES-PKCS1-v1_5) and signature schemes (RSASSA-PSS, RSASSA-PKCS1-v1_5).
RSA's security rests on the computational difficulty of factoring the
product of two large primes; NIST SP 800-57 currently recommends a
minimum RSA modulus size of 2048 bits for near-term use and 3072 bits
for security through 2030 and beyond, with 1024-bit RSA considered
too weak for new systems.

The commonly used public exponent e = 65537 (0x10001) balances
encryption performance against known small-exponent attacks. Because
RSA key generation, padding scheme choice, and exponent selection all
materially affect real-world security, RSA implementations are
frequently evaluated not just on key size but on whether they use a
modern padding scheme (OAEP/PSS) rather than the legacy PKCS1-v1.5
padding, which is vulnerable to padding-oracle attacks (e.g. the
Bleichenbacher attack) in some deployment configurations.
