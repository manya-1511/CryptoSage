---
title: MITRE CWE-327 — Use of a Broken or Risky Cryptographic Algorithm
source_type: MITRE
identifier: CWE-327
---

# CWE-327: Use of a Broken or Risky Cryptographic Algorithm

CWE-327 describes the weakness of using a cryptographic algorithm that
is inherently insecure for the context in which it is deployed --
either because the algorithm has known practical breaks (e.g. DES's
56-bit keyspace being brute-forceable, RC4's keystream biases, MD5 and
SHA-1's collision vulnerabilities), or because it provides insufficient
security margin for the sensitivity/lifetime of the data it protects.

Software that hardcodes or defaults to such an algorithm -- rather
than a currently-recommended one such as AES, ChaCha20, or SHA-256/3 --
is flagged under this weakness class regardless of whether the
surrounding implementation is otherwise correct, since the algorithm
choice itself is the root cause of the exposure. Mitigation is to
migrate to an algorithm and key length combination that meets current
NIST or equivalent authoritative guidance (see NIST SP 800-131A).
