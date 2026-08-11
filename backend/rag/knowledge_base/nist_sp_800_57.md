---
title: NIST SP 800-57 Part 1 — Recommendation for Key Management
source_type: NIST
identifier: SP 800-57 Part 1 Rev. 5
---

# Key Management and Cryptographic Algorithm Lifecycle Guidance

NIST Special Publication 800-57 Part 1 provides general guidance on
cryptographic key management, including recommended key lengths and
the approved status of common algorithms over time. It defines the
security-strength categories NIST uses to evaluate whether an
algorithm and key length combination remains acceptable for protecting
federal information, and it documents the phased deprecation timeline
NIST has applied to algorithms as cryptanalysis and computing power
advance.

Under SP 800-57, AES (all key sizes), SHA-256/384/512, and elliptic
curve algorithms using NIST-approved curves at adequate key sizes are
categorized as providing strong, currently-approved security. Two-key
and three-key Triple DES (3DES/TDEA), 80-bit and smaller symmetric key
strengths, and hash functions with fewer than 224 bits of output (e.g.
plain SHA-1 for digital signatures) are treated as legacy-use-only or
disallowed for new systems, consistent with the transition guidance in
SP 800-131A.

Regardless of algorithm strength, SP 800-57 emphasizes that secure key
generation, storage, distribution, and destruction practices are a
precondition for any cryptographic algorithm to provide its intended
protection -- a strong algorithm with a hardcoded or poorly-protected
key provides materially weaker real-world security than its
theoretical strength suggests.
