---
title: RFC 8439 — ChaCha20 and Poly1305 for IETF Protocols
source_type: RFC
identifier: RFC 8439
---

# ChaCha20 and Poly1305

RFC 8439 (obsoleting the earlier RFC 7539) specifies the ChaCha20
stream cipher and the Poly1305 message authentication code, along with
their combined AEAD (Authenticated Encryption with Associated Data)
construction, ChaCha20-Poly1305. ChaCha20 is a 256-bit-key stream
cipher designed by Daniel J. Bernstein as a variant of Salsa20, using
a 20-round ARX (add-rotate-xor) structure that is efficient in software
without dedicated hardware acceleration, unlike AES-NI-dependent AES
implementations.

ChaCha20-Poly1305 is widely deployed as a TLS 1.3 cipher suite and is
generally considered to have a comparable security margin to AES-256-
GCM, while offering more consistent performance on platforms lacking
AES hardware acceleration (e.g. many embedded and mobile devices) and
greater resistance to timing side-channel attacks due to its
branch-free, table-free design. It is a commonly recommended
replacement for RC4 in software-only environments.
