---
title: OWASP Internet of Things Top 10
source_type: OWASP
identifier: OWASP IoT Top 10 (2018)
---

# OWASP IoT Top 10

The OWASP IoT Top 10 identifies the most critical security risks
affecting Internet of Things devices and firmware. Several items are
directly relevant to firmware cryptographic implementation analysis:

- **I1 -- Weak, Guessable, or Hardcoded Passwords**: includes hardcoded
  cryptographic keys and credentials embedded in firmware images.
- **I5 -- Use of Insecure or Outdated Components**: covers firmware
  that relies on deprecated cryptographic libraries or algorithm
  implementations (e.g. unpatched OpenSSL versions, DES/RC4-based
  legacy protocol stacks).
- **I7 -- Insecure Data Transfer and Storage**: covers firmware that
  fails to encrypt sensitive data at rest or in transit, or that uses
  a cryptographically weak algorithm to do so.
- **I9 -- Insecure Default Settings**: covers firmware shipped with
  debug interfaces, verbose logging, or weakened default
  cryptographic configurations still enabled in production.

The OWASP IoT Top 10 is commonly cited alongside NIST/MITRE guidance
when assessing embedded and firmware cryptographic posture, since it
frames the same underlying weaknesses (weak algorithms, hardcoded
secrets, debug artifacts) specifically in the context of constrained,
often unpatchable IoT/embedded deployments.
